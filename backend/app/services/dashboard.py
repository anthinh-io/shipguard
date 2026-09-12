from datetime import date, datetime, time, timedelta

import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.derived import orders

# Bộ Olist thực chất kết thúc tháng 8/2018: tháng 9 chỉ còn 56 đơn giao, tháng 10 chỉ
# còn 3. Không có ngưỡng thì kỳ mặc định kéo tới tận những tháng đó, tỷ lệ dựng trên
# mẫu vài đơn và màn hình trông như hệ thống hỏng chứ không phải như dữ liệu đã hết.
FULL_MONTH_MIN_DELIVERED_ORDERS = 100
DEFAULT_PERIOD_MONTHS = 12

# Delivered Order theo CONTEXT.md: đơn đã tới tay khách và có ngày giao thực tế. Đây là
# tập đơn duy nhất được tính vào KPI — bảng dẫn xuất cố ý giữ mọi đơn kèm cột trạng
# thái, việc lọc thuộc về truy vấn KPI. Dựng bằng Core chứ không phải chuỗi SQL để các
# truy vấn sau còn ghép thêm điều kiện lọc và mệnh đề gom nhóm lên trên.
DELIVERED = sa.and_(
    orders.c.order_status == "delivered",
    orders.c.delivered_to_customer_at.is_not(None),
)


class ReportingPeriod(BaseModel):
    start_date: date
    end_date: date


class StageDuration(BaseModel):
    median_days: float | None
    p90_days: float | None


class DashboardKpis(BaseModel):
    delivered_orders: int
    late_orders: int
    on_time_rate: float | None
    payment_approval: StageDuration
    seller_handling: StageDuration
    carrier_transit: StageDuration
    late_related_low_review_rate: float | None


async def resolve_default_period(session: AsyncSession) -> ReportingPeriod | None:
    """Kỳ mặc định: 12 tháng gần nhất tính đến tháng đầy đủ cuối cùng.

    Không tháng nào đạt ngưỡng thì lùi về tháng cuối cùng có đơn đã giao. Trả None chỉ
    khi không có đơn đã giao nào — lúc đó không có kỳ nào suy ra được từ dữ liệu.
    """
    month = sa.func.date_trunc("month", orders.c.delivered_to_customer_at)
    monthly = (
        sa.select(month.label("month"), sa.func.count().label("delivered"))
        .where(DELIVERED)
        .group_by(month)
        .cte("monthly")
    )
    # FILTER không áp được lên aggregate của một aggregate ở cùng một tầng, nên phải
    # qua CTE. coalesce gộp luôn nhánh dự phòng vào đây để không tốn lượt đi về thứ hai.
    chosen = sa.select(
        sa.func.coalesce(
            sa.func.max(monthly.c.month).filter(
                monthly.c.delivered >= FULL_MONTH_MIN_DELIVERED_ORDERS
            ),
            sa.func.max(monthly.c.month),
        ).label("end_month")
    ).cte("chosen")
    first_of_end_month = sa.cast(chosen.c.end_month, sa.Date)
    row = (
        await session.execute(
            sa.select(
                sa.cast(
                    chosen.c.end_month
                    - sa.func.make_interval(0, DEFAULT_PERIOD_MONTHS - 1),
                    sa.Date,
                ).label("start_date"),
                (
                    sa.cast(
                        chosen.c.end_month + sa.func.make_interval(0, 1), sa.Date
                    )
                    - 1
                ).label("end_date"),
            ).where(first_of_end_month.is_not(None))
        )
    ).one_or_none()
    if row is None:
        return None
    return ReportingPeriod(start_date=row.start_date, end_date=row.end_date)


def _stage_percentiles(
    column: sa.ColumnElement,
) -> tuple[sa.ColumnElement, sa.ColumnElement]:
    # Cột chặng là INTERVAL; percentile_cont cần một biểu thức số. epoch/86400 quy đổi
    # sang số ngày dạng float. percentile_cont tự bỏ qua NULL, nên các đơn thiếu mốc
    # trung gian (chưa bàn giao cho vận chuyển, v.v.) không kéo lệch kết quả — mẫu số
    # của một chặng vốn khác mẫu số đơn đã giao, và đó là đúng.
    #
    # Trung vị và phân vị 90, không dùng trung bình cộng: cả ba chặng lệch đuôi mạnh,
    # một nhúm đơn cá biệt kéo trung bình lệch xa giá trị điển hình (xem CONTEXT.md).
    days = sa.extract("epoch", column) / 86400.0
    return (
        sa.func.percentile_cont(0.5).within_group(days),
        sa.func.percentile_cont(0.9).within_group(days),
    )


async def compute_kpis(
    session: AsyncSession, period: ReportingPeriod | None
) -> DashboardKpis:
    """Tỷ lệ giao đúng hạn, số đơn trễ, ba chặng thời gian và tỷ lệ đánh giá thấp do
    trễ — tất cả trên tập đơn đã giao.

    `period` là None nghĩa là không lọc kỳ nào. Hai đường dẫn tới đó: test đối chiếu bộ
    số vàng trên toàn bộ dữ liệu, và trường hợp `resolve_default_period` không suy ra
    được kỳ nào vì chưa có đơn đã giao.

    Hàm này không tự giải kỳ mặc định; việc đó thuộc về route, để bên gọi còn hỏi được
    con số trên toàn bộ dữ liệu.
    """
    payment_approval_med, payment_approval_p90 = _stage_percentiles(
        orders.c.payment_approval
    )
    seller_handling_med, seller_handling_p90 = _stage_percentiles(
        orders.c.seller_handling
    )
    carrier_transit_med, carrier_transit_p90 = _stage_percentiles(
        orders.c.carrier_transit
    )
    # Mẫu số là đơn bị chấm 1–2 sao, tử số là số đơn trong đó bị giao trễ. Ba sao là
    # trung tính nên bị loại khỏi cả hai vế; đơn không có đánh giá nào cũng bị loại vì
    # so sánh với NULL không bao giờ đúng. Chiều ngược lại (đơn trễ / có đánh giá thấp)
    # trả lời một câu hỏi khác — xem CONTEXT.md mục Late-Related Low Review Rate.
    low_review = orders.c.worst_review_score <= 2
    low_reviews = sa.func.count().filter(low_review)
    low_and_late = sa.func.count().filter(
        sa.and_(low_review, orders.c.is_late.is_(True))
    )

    statement = sa.select(
        sa.func.count(),
        # is_late là NULL với đơn chưa giao, nên WHERE is_late lẫn WHERE NOT is_late
        # đều lặng lẽ bỏ chúng. Vị ngữ DELIVERED đã loại hết nhóm đó rồi, IS TRUE ở đây
        # là để nói rõ ý định.
        sa.func.count().filter(orders.c.is_late.is_(True)),
        payment_approval_med,
        payment_approval_p90,
        seller_handling_med,
        seller_handling_p90,
        carrier_transit_med,
        carrier_transit_p90,
        low_reviews,
        low_and_late,
    ).where(DELIVERED)
    if period is not None:
        statement = statement.where(_delivered_within(period))

    row = (await session.execute(statement)).one()
    (
        delivered_orders,
        late_orders,
        pa_med,
        pa_p90,
        sh_med,
        sh_p90,
        ct_med,
        ct_p90,
        low_reviews_count,
        low_and_late_count,
    ) = row
    on_time_rate = (
        None
        if delivered_orders == 0
        else (delivered_orders - late_orders) / delivered_orders
    )
    late_related_low_review_rate = (
        None if low_reviews_count == 0 else low_and_late_count / low_reviews_count
    )
    return DashboardKpis(
        delivered_orders=delivered_orders,
        late_orders=late_orders,
        on_time_rate=on_time_rate,
        payment_approval=StageDuration(median_days=pa_med, p90_days=pa_p90),
        seller_handling=StageDuration(median_days=sh_med, p90_days=sh_p90),
        carrier_transit=StageDuration(median_days=ct_med, p90_days=ct_p90),
        late_related_low_review_rate=late_related_low_review_rate,
    )


def _delivered_within(period: ReportingPeriod) -> sa.ColumnElement[bool]:
    # Chặn bằng dấu thời gian thay vì ép delivered_to_customer_at::date, để chỉ mục
    # ix_orders_delivered_to_customer_at còn dùng được. Cận trên là nửa đêm đầu ngày kế
    # tiếp, nên kết quả trùng khít với phép so ở mức ngày lịch.
    return sa.and_(
        orders.c.delivered_to_customer_at >= datetime.combine(
            period.start_date, time.min
        ),
        orders.c.delivered_to_customer_at
        < datetime.combine(period.end_date + timedelta(days=1), time.min),
    )
