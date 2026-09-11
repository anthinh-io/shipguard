import json
from datetime import date
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.dashboard import (
    DEFAULT_PERIOD_MONTHS,
    FULL_MONTH_MIN_DELIVERED_ORDERS,
    ReportingPeriod,
    compute_kpis,
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
