import json
from datetime import date, timedelta
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.dashboard import (
    DEFAULT_PERIOD_MONTHS,
    FULL_MONTH_MIN_DELIVERED_ORDERS,
    ReportingPeriod,
    choose_granularity,
    compute_kpis,
    compute_late_rate_trend,
    resolve_default_period,
)

EDGE_CASE_ORDERS = json.loads(
    (Path(__file__).parent / "fixtures" / "edge_case_orders.json").read_text("utf-8")
)

ORDER_IDS = bindparam("ids", type_=sa.ARRAY(sa.Text))

DELIVERED_MONTHS = (
    "SELECT date_trunc('month', delivered_to_customer_at) AS month, "
    "count(*) AS delivered FROM orders "
    "WHERE order_status = 'delivered' AND delivered_to_customer_at IS NOT NULL "
    "GROUP BY 1"
)


async def test_on_time_rate_over_unfiltered_data(session: AsyncSession) -> None:
    kpis = await compute_kpis(session, None)

    assert kpis.delivered_orders == 96470
    assert kpis.late_orders == 6534
    assert kpis.on_time_rate is not None
    assert round(kpis.on_time_rate * 100, 2) == 93.23


async def test_stage_durations_over_unfiltered_data(session: AsyncSession) -> None:
    kpis = await compute_kpis(session, None)

    # Bộ số vàng của #8, tính bằng ngày, làm tròn 2 chữ số. Trung vị và phân vị 90 —
    # không có trung bình cộng nào ở đây vì cả ba chặng lệch đuôi mạnh.
    assert round(kpis.payment_approval.median_days, 2) == 0.01
    assert round(kpis.payment_approval.p90_days, 2) == 1.44
    assert round(kpis.seller_handling.median_days, 2) == 1.82
    assert round(kpis.seller_handling.p90_days, 2) == 5.99
    assert round(kpis.carrier_transit.median_days, 2) == 7.10
    assert round(kpis.carrier_transit.p90_days, 2) == 18.90


async def test_late_related_low_review_rate_over_unfiltered_data(
    session: AsyncSession,
) -> None:
    kpis = await compute_kpis(session, None)

    assert kpis.late_related_low_review_rate is not None
    rate = round(kpis.late_related_low_review_rate * 100, 2)
    assert rate == 32.38
    # 62,47% là tỷ lệ tính ngược chiều: đơn trễ bị chấm 1–2 sao / đơn trễ có đánh giá.
    # Ra đúng con số này nghĩa là mẫu số và tử số đã bị đảo — xem CONTEXT.md mục
    # Late-Related Low Review Rate.
    assert rate != 62.47


async def test_three_star_orders_are_not_low_reviews(session: AsyncSession) -> None:
    # Đếm lại mẫu số bằng một truy vấn độc lập với worst_review_score <= 2, rồi khẳng
    # định có tồn tại đơn 3 sao — nếu không có đơn 3 sao nào thì bài test này không
    # phân biệt được "loại 3 sao" với "không có đơn 3 sao nào để loại".
    low_review_count = await session.scalar(
        text(
            "SELECT count(*) FROM orders WHERE order_status = 'delivered' "
            "AND delivered_to_customer_at IS NOT NULL AND worst_review_score <= 2"
        )
    )
    three_star_count = await session.scalar(
        text(
            "SELECT count(*) FROM orders WHERE order_status = 'delivered' "
            "AND delivered_to_customer_at IS NOT NULL AND worst_review_score = 3"
        )
    )

    assert three_star_count > 0
    assert low_review_count == 12310


def test_granularity_switches_at_the_31_day_boundary() -> None:
    start = date(2018, 1, 1)

    # Kỳ 30 ngày (điểm cuối trong khoảng 29 ngày sau điểm đầu).
    thirty_days = ReportingPeriod(start_date=start, end_date=start + timedelta(days=29))
    # Kỳ 31 ngày — vượt ranh giới đúng một ngày.
    thirty_one_days = ReportingPeriod(
        start_date=start, end_date=start + timedelta(days=30)
    )

    assert choose_granularity(thirty_days) == "day"
    assert choose_granularity(thirty_one_days) == "week"


def test_granularity_switches_at_the_six_month_boundary() -> None:
    start = date(2018, 1, 1)

    # 182 ngày — "dưới 6 tháng" quy về ngày.
    span_182 = ReportingPeriod(start_date=start, end_date=start + timedelta(days=181))
    # 183 ngày — vượt ranh giới đúng một ngày.
    span_183 = ReportingPeriod(start_date=start, end_date=start + timedelta(days=182))

    assert choose_granularity(span_182) == "week"
    assert choose_granularity(span_183) == "month"


async def test_trend_fills_empty_buckets(session: AsyncSession) -> None:
    # Cuối dải dữ liệu Olist: chỉ 10/10 và 10/17 có đơn giao, sáu ngày ở giữa không có
    # đơn nào. Gom nhóm trần sẽ chỉ trả về hai điểm; lấp khoảng trống phải trả đủ 8.
    period = ReportingPeriod(start_date=date(2018, 10, 10), end_date=date(2018, 10, 17))

    trend = await compute_late_rate_trend(session, period)

    assert trend.granularity == "day"
    assert len(trend.points) == 8
    by_date = {point.bucket_start: point for point in trend.points}
    # Nhóm rỗng: không có đơn nào, và late_rate là None — không phải 0%.
    assert by_date[date(2018, 10, 12)].delivered_orders == 0
    assert by_date[date(2018, 10, 12)].late_rate is None
    # Hai ngày có đơn thật vẫn đếm đúng.
    assert by_date[date(2018, 10, 11)].delivered_orders == 1
    assert by_date[date(2018, 10, 17)].delivered_orders == 1


async def test_trend_over_unfiltered_default_period_has_no_gaps(
    session: AsyncSession,
) -> None:
    # Kỳ mặc định trùng khít mốc tháng nên không dính hiện tượng nhóm khuyết ở hai đầu;
    # 12 tháng phải cho ra đúng 12 điểm, không thiếu điểm nào.
    period = await resolve_default_period(session)
    assert period is not None

    trend = await compute_late_rate_trend(session, period)

    assert trend.granularity == "month"
    assert len(trend.points) == 12
    assert all(point.delivered_orders > 0 for point in trend.points)


async def test_default_period_ends_at_the_last_full_month(
    session: AsyncSession,
) -> None:
    # Tháng kết thúc tính lại từ dữ liệu bằng truy vấn riêng của bài test, để khẳng
    # định kỳ mặc định suy ra từ dữ liệu chứ không phải từ một ngày đóng cứng trong mã.
    expected_end_month = await session.scalar(
        text(f"SELECT max(month) FROM ({DELIVERED_MONTHS}) m WHERE delivered >= :n"),
        {"n": FULL_MONTH_MIN_DELIVERED_ORDERS},
    )

    period = await resolve_default_period(session)

    assert period is not None
    assert period.end_date.replace(day=1) == expected_end_month.date()
    # Trên bộ Olist, tháng đầy đủ cuối cùng là 8/2018: tháng 9 chỉ có 56 đơn giao.
    assert period.start_date == date(2017, 9, 1)
    assert period.end_date == date(2018, 8, 31)
    assert _months_spanned(period) == DEFAULT_PERIOD_MONTHS


async def test_default_period_falls_back_when_no_month_is_full(
    session: AsyncSession,
) -> None:
    every_id = sorted({o for group in EDGE_CASE_ORDERS.values() for o in group})
    try:
        # Thu bảng về tập con cố định ngay trong transaction rồi rollback ở finally.
        # Dịch vụ nhận đúng session này nên nó thấy thao tác xoá chưa commit. Khoá
        # ngoại quy định thứ tự: bảng nối trước, bảng cha sau.
        for table in ("order_sellers", "orders"):
            await session.execute(
                text(f"DELETE FROM {table} WHERE order_id <> ALL(:ids)").bindparams(
                    ORDER_IDS
                ),
                {"ids": every_id},
            )

        # Tiền đề của chính bài test. Thiếu khẳng định này, một lần sửa fixture sau
        # này đẩy một tháng vượt ngưỡng sẽ âm thầm lái test sang nhánh chính mà vẫn
        # xanh, và nhánh dự phòng mất phủ mà không ai biết.
        busiest_month = await session.scalar(
            text(f"SELECT max(delivered) FROM ({DELIVERED_MONTHS}) m")
        )
        assert 0 < busiest_month < FULL_MONTH_MIN_DELIVERED_ORDERS

        period = await resolve_default_period(session)

        assert period is not None
        # Không tháng nào đạt ngưỡng, nên lùi về tháng cuối cùng có đơn đã giao —
        # 9/2018, khác hẳn tháng kết thúc của nhánh chính.
        assert period.start_date == date(2017, 10, 1)
        assert period.end_date == date(2018, 9, 30)
        assert _months_spanned(period) == DEFAULT_PERIOD_MONTHS
    finally:
        await session.rollback()


def _months_spanned(period: ReportingPeriod) -> int:
    start, end = period.start_date, period.end_date
    return (end.year - start.year) * 12 + end.month - start.month + 1
