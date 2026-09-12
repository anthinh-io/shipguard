import json
from datetime import date
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

EDGE_CASE_FILTERS = json.loads(
    (Path(__file__).parent / "fixtures" / "edge_case_filters.json").read_text("utf-8")
)

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
        "filter_options",
        "kpis",
        "late_rate_trend",
        "late_rate_by_state",
        "small_sample",
    }
    assert set(body["reporting_period"]) == {"start_date", "end_date"}
    assert set(body["filter_options"]) == {"customer_states"}
    assert len(body["filter_options"]["customer_states"]) == 27
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


async def test_customer_state_filter_narrows_response(
    client: AsyncClient, session: AsyncSession
) -> None:
    expected_delivered = await session.scalar(
        text(
            "SELECT count(*) FROM orders WHERE order_status = 'delivered' "
            "AND delivered_to_customer_at IS NOT NULL AND customer_state = 'AL'"
        )
    )

    # Trải rộng qua toàn bộ dải dữ liệu Olist để không lẫn với kỳ mặc định — nếu không
    # gọi params, route tự giải kỳ mặc định và con số sẽ lệch với truy vấn không lọc kỳ
    # ở trên.
    params = {
        "start_date": "2016-01-01",
        "end_date": "2018-12-31",
        "customer_state": "AL",
    }
    body = (await client.get("/dashboard", params=params)).json()

    assert body["kpis"]["delivered_orders"] == expected_delivered
    assert len(body["late_rate_by_state"]) == 1
    assert body["late_rate_by_state"][0]["customer_state"] == "AL"
    # filter_options không bị ảnh hưởng bởi bộ lọc đang áp dụng — ô chọn vẫn đủ 27 bang.
    assert len(body["filter_options"]["customer_states"]) == 27


async def test_filters_matching_no_orders_return_empty_not_an_error(
    client: AsyncClient,
) -> None:
    # Khoảng ngày ngoài dải dữ liệu Olist (2016–2018): không đơn nào khớp, nhưng đây là
    # một kết quả rỗng hợp lệ, không phải lỗi hệ thống — phản hồi vẫn phải là 200.
    params = {"start_date": "2010-01-01", "end_date": "2010-01-02"}

    response = await client.get("/dashboard", params=params)

    assert response.status_code == 200
    body = response.json()
    assert body["kpis"]["delivered_orders"] == 0
    assert body["kpis"]["on_time_rate"] is None
    assert body["late_rate_by_state"] == []


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


async def test_seller_filter_combines_with_state_and_period(
    client: AsyncClient,
) -> None:
    seller_id = EDGE_CASE_FILTERS["busiest_seller"]
    whole_range = {"start_date": "2016-01-01", "end_date": "2018-12-31"}

    seller_only = (
        await client.get("/dashboard", params={**whole_range, "seller_id": seller_id})
    ).json()
    combined = (
        await client.get(
            "/dashboard",
            params={
                "start_date": "2018-01-01",
                "end_date": "2018-06-30",
                "customer_state": "SP",
                "seller_id": seller_id,
            },
        )
    ).json()

    # Ba chiều lọc chồng lên nhau cùng lúc, không cái nào ghi đè cái nào.
    assert 0 < combined["kpis"]["delivered_orders"] < seller_only["kpis"]["delivered_orders"]
    # Tuỳ chọn bộ lọc không bị bộ lọc đang áp làm hẹp lại.
    assert len(combined["filter_options"]["customer_states"]) == 27


async def test_small_sample_flag_follows_the_filtered_order_count(
    client: AsyncClient,
) -> None:
    small_seller = EDGE_CASE_FILTERS["small_sample_sellers"][0]
    busiest_seller = EDGE_CASE_FILTERS["busiest_seller"]
    whole_range = {"start_date": "2016-01-01", "end_date": "2018-12-31"}

    small = (
        await client.get("/dashboard", params={**whole_range, "seller_id": small_seller})
    ).json()
    large = (
        await client.get(
            "/dashboard", params={**whole_range, "seller_id": busiest_seller}
        )
    ).json()

    assert small["small_sample"] is True
    assert 0 < small["kpis"]["delivered_orders"] < 30
    # Số liệu vẫn về đầy đủ khi bị gắn cờ — cờ chỉ cảnh báo, không ẩn gì cả.
    assert small["kpis"]["on_time_rate"] is not None
    assert small["late_rate_by_state"] != []

    assert large["small_sample"] is False
    assert large["kpis"]["delivered_orders"] >= 30


async def test_sellers_endpoint_returns_suggestions_with_state_and_count(
    client: AsyncClient,
) -> None:
    seller_id = EDGE_CASE_FILTERS["busiest_seller"]

    response = await client.get("/sellers", params={"q": seller_id[:8]})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert set(body[0]) == {
        "seller_id",
        "seller_city",
        "seller_state",
        "delivered_orders",
    }
    assert body[0]["seller_id"] == seller_id
    # Mã băm trông giống hệt nhau; bang và số đơn là hai thứ phân biệt được các dòng.
    assert body[0]["seller_state"] == "SP"
    assert body[0]["delivered_orders"] > 0


async def test_sellers_endpoint_honours_the_limit(client: AsyncClient) -> None:
    body = (await client.get("/sellers", params={"q": "SP", "limit": 3})).json()

    assert len(body) == 3


@pytest.mark.parametrize("params", [{}, {"q": ""}, {"q": "   "}], ids=["none", "empty", "blank"])
async def test_sellers_endpoint_returns_nothing_without_a_query(
    client: AsyncClient, params: dict[str, str]
) -> None:
    # Không gõ gì thì không có gợi ý nào — đổ cả nghìn dòng ra không phải là gợi ý.
    response = await client.get("/sellers", params=params)

    assert response.status_code == 200
    assert response.json() == []


async def test_cors_header_present_for_an_allowed_origin(
    client: AsyncClient,
) -> None:
    origin = settings.CORS_ALLOWED_ORIGINS[0]

    response = await client.get("/dashboard", headers={"Origin": origin})

    # Trình duyệt gọi thẳng backend, nên thiếu header này là màn hình trắng mà không có
    # lỗi nào ở phía máy chủ. Danh sách origin lệch giữa các môi trường là chỗ hỏng
    # kinh điển của cách gọi này.
    assert response.headers["access-control-allow-origin"] == origin
