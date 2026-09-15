from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import SessionDep, get_current_user
from app.services.dashboard import (
    ComparisonMode,
    DashboardFilters,
    DashboardKpis,
    LateRateTrend,
    ReportingPeriod,
    SellerOption,
    StateLateRate,
    choose_granularity,
    compute_kpis,
    compute_late_rate_by_state,
    compute_late_rate_trend,
    is_small_sample,
    list_customer_states,
    resolve_comparison_period,
    resolve_default_period,
    search_sellers,
)

# Khóa ở mức router chứ không gắn vào từng handler: route số liệu không cần biết ai đang
# gọi, chỉ cần chắc là đã đăng nhập — và route mới thêm vào đây tự được khóa theo.
router = APIRouter(tags=["dashboard"], dependencies=[Depends(get_current_user)])


class FilterOptions(BaseModel):
    # Không áp bộ lọc nào khi tính: chọn một bang không được làm biến mất các lựa chọn
    # còn lại trong ô chọn.
    customer_states: list[str]


# Một endpoint tổng hợp nhận mọi điều kiện lọc và trả mọi số liệu của bảng điều khiển
# trong một lần gọi. "Một lần gọi" ở đây là một lần gọi HTTP, không phải một câu SQL:
# route chạy nhiều truy vấn (giải kỳ, rồi tính từng khối) và như vậy là đúng. Mỗi khối
# lồng riêng để các chỉ số về sau nối thêm mà không phải đổi hình dạng phản hồi.
class DashboardResponse(BaseModel):
    reporting_period: ReportingPeriod | None
    filter_options: FilterOptions
    kpis: DashboardKpis
    late_rate_trend: LateRateTrend
    late_rate_by_state: list[StateLateRate]
    # Chỉ là một cờ cảnh báo: số liệu bên trên vẫn đầy đủ. Người dùng có quyền xem, chỉ
    # cần biết là đừng kết luận chắc từ một tập vài đơn.
    small_sample: bool
    # Ba khối của kỳ đối chiếu, cùng về trong một lần gọi. None nghĩa là không so sánh —
    # khác hẳn với "có so sánh nhưng kỳ đối chiếu rỗng", trường hợp đó vẫn có khối đầy
    # đủ với delivered_orders bằng 0 và các tỷ lệ là None.
    #
    # Phân bố theo bang cố ý không có bản đối chiếu: đặc tả ở #1 chỉ yêu cầu chuỗi đối
    # chiếu cho ô KPI và biểu đồ xu hướng.
    comparison_period: ReportingPeriod | None
    comparison_kpis: DashboardKpis | None
    comparison_late_rate_trend: LateRateTrend | None


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    session: SessionDep,
    start_date: date | None = None,
    end_date: date | None = None,
    # Đặt tên customer_state chứ không phải state: cái bẫy dễ nhầm nhất của phân bố
    # theo bang là lẫn bang người bán với bang khách nhận (xem CONTEXT.md mục Region).
    customer_state: str | None = None,
    seller_id: str | None = None,
    comparison: ComparisonMode = "none",
) -> DashboardResponse:
    if (start_date is None) != (end_date is None):
        raise HTTPException(
            status_code=422,
            detail="start_date and end_date must be given together, or both omitted",
        )

    period = (
        ReportingPeriod(start_date=start_date, end_date=end_date)
        if start_date is not None and end_date is not None
        else await resolve_default_period(session)
    )
    filters = DashboardFilters(
        period=period, customer_state=customer_state, seller_id=seller_id
    )
    customer_states = await list_customer_states(session)
    kpis = await compute_kpis(session, filters)

    comparison_period = resolve_comparison_period(period, comparison)
    comparison_kpis = None
    comparison_trend = None
    if comparison_period is not None:
        # Chỉ kỳ đổi; bang và người bán áp nguyên vẹn cho cả hai vế, nếu không thì mức
        # chênh đang so hai tập đơn khác nhau về bản chất.
        comparison_filters = filters.model_copy(update={"period": comparison_period})
        comparison_kpis = await compute_kpis(session, comparison_filters)
        # Áp độ mịn của kỳ chính thay vì để kỳ đối chiếu tự chọn: hai kỳ "cùng kỳ năm
        # trước" có thể lệch nhau một ngày vì năm nhuận, đủ để rơi vào hai độ mịn khác
        # nhau, và hai đường như vậy không chồng lên nhau được.
        comparison_trend = await compute_late_rate_trend(
            session,
            comparison_filters,
            granularity=None if period is None else choose_granularity(period),
        )

    return DashboardResponse(
        reporting_period=period,
        filter_options=FilterOptions(customer_states=customer_states),
        kpis=kpis,
        late_rate_trend=await compute_late_rate_trend(session, filters),
        late_rate_by_state=await compute_late_rate_by_state(session, filters),
        small_sample=is_small_sample(kpis.delivered_orders),
        comparison_period=comparison_period,
        comparison_kpis=comparison_kpis,
        comparison_late_rate_trend=comparison_trend,
    )


# Endpoint phụ trả tuỳ chọn cho bộ lọc. Tách khỏi /dashboard vì ~3 nghìn người bán
# không nhồi được vào mọi phản hồi, và vì ô gõ dần gọi lại theo từng phím gõ — một
# luồng hoàn toàn khác với "một lần đổi bộ lọc, một lần gọi" của bảng điều khiển.
#
# Đường dẫn ngang hàng /dashboard chứ không phải /dashboard/sellers: mẫu chặn của
# Playwright là `${BACKEND_URL}/dashboard**`, mà `**` vượt cả dấu gạch chéo.
@router.get("/sellers", response_model=list[SellerOption])
async def sellers(
    session: SessionDep,
    q: str = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    # Bảng điều khiển chỉ tính đơn đã giao nên mặc định chỉ gợi ý người bán có đơn đã
    # giao. Danh sách đơn gửi false để chọn được cả người bán chưa có đơn nào giao xong.
    delivered_only: bool = True,
) -> list[SellerOption]:
    return await search_sellers(session, q, limit, delivered_only=delivered_only)
