from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import SessionDep
from app.services.dashboard import (
    DashboardFilters,
    DashboardKpis,
    LateRateTrend,
    ReportingPeriod,
    SellerOption,
    StateLateRate,
    compute_kpis,
    compute_late_rate_by_state,
    compute_late_rate_trend,
    is_small_sample,
    list_customer_states,
    resolve_default_period,
    search_sellers,
)

router = APIRouter(tags=["dashboard"])


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


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    session: SessionDep,
    start_date: date | None = None,
    end_date: date | None = None,
    # Đặt tên customer_state chứ không phải state: cái bẫy dễ nhầm nhất của phân bố
    # theo bang là lẫn bang người bán với bang khách nhận (xem CONTEXT.md mục Region).
    customer_state: str | None = None,
    seller_id: str | None = None,
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
    return DashboardResponse(
        reporting_period=period,
        filter_options=FilterOptions(customer_states=customer_states),
        kpis=kpis,
        late_rate_trend=await compute_late_rate_trend(session, filters),
        late_rate_by_state=await compute_late_rate_by_state(session, filters),
        small_sample=is_small_sample(kpis.delivered_orders),
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
) -> list[SellerOption]:
    return await search_sellers(session, q, limit)
