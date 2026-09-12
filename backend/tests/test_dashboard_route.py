from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

# Fixture client của conftest chỉ phụ thuộc DSN, không kéo theo bước nạp dữ liệu. Thiếu
# ràng buộc này thì tệp chạy riêng sẽ đọc một bảng rỗng và xanh sai.
pytestmark = pytest.mark.usefixtures("derived_data")

# Một kỳ nằm gọn trong dải dữ liệu, đủ dài để số đơn theo ngày giao và số đơn theo ngày
# đặt lệch hẳn nhau.
REPORTING_PERIOD = {"start_date": "2018-01-01", "end_date": "2018-03-31"}

COUNT_BY = (
    "SELECT count(*) FROM orders "
    "WHERE order_status = 'delivered' AND delivered_to_customer_at IS NOT NULL "
    "AND {column}::date BETWEEN :start AND :end"
)


async def test_response_shape(client: AsyncClient) -> None:
    response = await client.get("/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "reporting_period",
        "kpis",
        "late_rate_trend",
        "late_rate_by_state",
    }
    assert set(body["reporting_period"]) == {"start_date", "end_date"}
    assert set(body["kpis"]) == {
        "delivered_orders",
        "late_orders",
        "on_time_rate",
        "payment_approval",
        "seller_handling",
        "carrier_transit",
        "late_related_low_review_rate",
    }
    assert set(body["kpis"]["payment_approval"]) == {"median_days", "p90_days"}
    assert set(body["late_rate_trend"]) == {"granularity", "points"}
    if body["late_rate_trend"]["points"]:
        assert set(body["late_rate_trend"]["points"][0]) == {
            "bucket_start",
            "delivered_orders",
            "late_orders",
            "late_rate",
        }
    assert set(body["late_rate_by_state"][0]) == {
        "customer_state",
        "delivered_orders",
        "late_orders",
        "late_rate",
    }


async def test_default_period_applied_when_no_parameters_given(
    client: AsyncClient,
) -> None:
    body = (await client.get("/dashboard")).json()

    period = body["reporting_period"]
    assert period == {"start_date": "2017-09-01", "end_date": "2018-08-31"}
    # Kỳ mặc định loại bớt tháng nên con số ở đây phải khác bộ số vàng của tập không
    # lọc — 96.470 đơn, 93,23%. Khẳng định điều đó để không ai nhầm hai tập với nhau.
    assert body["kpis"]["delivered_orders"] < 96470


async def test_reporting_period_echoes_the_requested_period(
    client: AsyncClient,
) -> None:
    body = (await client.get("/dashboard", params=REPORTING_PERIOD)).json()

    assert body["reporting_period"] == REPORTING_PERIOD


async def test_period_filters_on_delivery_date_not_purchase_date(
    client: AsyncClient, session: AsyncSession
) -> None:
    bounds = {"start": date(2018, 1, 1), "end": date(2018, 3, 31)}
    by_delivery = await session.scalar(
        text(COUNT_BY.format(column="delivered_to_customer_at")), bounds
    )
    by_purchase = await session.scalar(
        text(COUNT_BY.format(column="purchased_at")), bounds
    )

    delivered = (await client.get("/dashboard", params=REPORTING_PERIOD)).json()["kpis"][
        "delivered_orders"
    ]

    # Hai con số phải lệch nhau, nếu không bài test này không phân biệt được gì cả.
    assert by_delivery != by_purchase
    assert delivered == by_delivery
    assert delivered != by_purchase


@pytest.mark.parametrize(
    "params",
    [{"start_date": "2018-01-01"}, {"end_date": "2018-03-31"}],
    ids=["only start_date", "only end_date"],
)
async def test_one_sided_period_is_rejected(
    client: AsyncClient, params: dict[str, str]
) -> None:
    response = await client.get("/dashboard", params=params)

    assert response.status_code == 422


async def test_cors_header_present_for_an_allowed_origin(
    client: AsyncClient,
) -> None:
    origin = settings.CORS_ALLOWED_ORIGINS[0]

    response = await client.get("/dashboard", headers={"Origin": origin})

    # Trình duyệt gọi thẳng backend, nên thiếu header này là màn hình trắng mà không có
    # lỗi nào ở phía máy chủ. Danh sách origin lệch giữa các môi trường là chỗ hỏng
    # kinh điển của cách gọi này.
    assert response.headers["access-control-allow-origin"] == origin
