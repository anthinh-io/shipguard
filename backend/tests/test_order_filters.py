import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from olist_csv import read_rows
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token

FIXTURES = Path(__file__).parent / "fixtures"
EDGE_CASE_ORDERS = json.loads((FIXTURES / "edge_case_orders.json").read_text("utf-8"))
EDGE_CASE_FILTERS = json.loads((FIXTURES / "edge_case_filters.json").read_text("utf-8"))

TOTAL_ORDERS = 99_441

# Bộ số vàng của #20, tính thẳng từ CSV ở test_golden_numbers_from_csv chứ không đi qua
# bảng dẫn xuất hay cột is_late — so một con số với chính nguồn sinh ra nó thì luôn xanh.
STATUS_COUNTS = {
    "delivered": 96_478,
    "shipped": 1_107,
    "canceled": 625,
    "unavailable": 609,
    "invoiced": 314,
    "processing": 301,
    "created": 5,
    "approved": 2,
}
OUTCOME_COUNTS = {"on_time": 89_936, "late": 6_534, "no_outcome": 2_971}
FIRST_PURCHASE_DAY = "2016-09-04"
LAST_PURCHASE_DAY = "2018-10-17"

# Hai con số bẫy: tính cả đơn đã hủy có ngày giao, và so nguyên dấu thời gian.
LATE_INCLUDING_CANCELED = 6_535
LATE_BY_TIMESTAMP = 7_826

pytestmark = pytest.mark.usefixtures("derived_data")


@pytest.fixture(autouse=True)
def signed_in(client: AsyncClient) -> None:
    token = create_access_token(1, "operations_staff", [])
    client.headers["Authorization"] = f"Bearer {token}"


async def get_orders(client: AsyncClient, **params: Any) -> dict[str, Any]:
    response = await client.get("/orders", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _csv_orders() -> tuple[dict[str, str], ...]:
    return read_rows("olist_orders_dataset.csv")


def _customer_states() -> dict[str, str]:
    return {
        row["customer_id"]: row["customer_state"]
        for row in read_rows("olist_customers_dataset.csv")
    }


def _sellers_by_order() -> dict[str, set[str]]:
    sellers: dict[str, set[str]] = defaultdict(set)
    for row in read_rows("olist_order_items_dataset.csv"):
        sellers[row["order_id"]].add(row["seller_id"])
    return sellers


def test_golden_numbers_from_csv() -> None:
    rows = _csv_orders()

    assert len(rows) == TOTAL_ORDERS
    assert Counter(row["order_status"] for row in rows) == STATUS_COUNTS

    # Delivery Outcome theo CONTEXT.md: chỉ đơn delivered có ngày giao mới đúng hạn hay
    # trễ, so ở mức ngày lịch — 10 ký tự đầu của hai chuỗi.
    outcomes: Counter[str] = Counter()
    for row in rows:
        delivered = row["order_delivered_customer_date"]
        if row["order_status"] != "delivered" or not delivered:
            outcomes["no_outcome"] += 1
        elif delivered[:10] > row["order_estimated_delivery_date"][:10]:
            outcomes["late"] += 1
        else:
            outcomes["on_time"] += 1
    assert outcomes == OUTCOME_COUNTS

    with_delivery_date = [row for row in rows if row["order_delivered_customer_date"]]
    assert (
        sum(
            1
            for row in with_delivery_date
            if row["order_status"] in {"delivered", "canceled"}
            and row["order_delivered_customer_date"][:10]
            > row["order_estimated_delivery_date"][:10]
        )
        == LATE_INCLUDING_CANCELED
    )
    assert (
        sum(
            1
            for row in with_delivery_date
            if row["order_status"] == "delivered"
            and row["order_delivered_customer_date"] > row["order_estimated_delivery_date"]
        )
        == LATE_BY_TIMESTAMP
    )

    purchase_days = sorted(row["order_purchase_timestamp"][:10] for row in rows)
    assert (purchase_days[0], purchase_days[-1]) == (FIRST_PURCHASE_DAY, LAST_PURCHASE_DAY)


@pytest.mark.parametrize(("status", "expected"), STATUS_COUNTS.items())
async def test_status_filter_matches_the_golden_count(
    client: AsyncClient, status: str, expected: int
) -> None:
    body = await get_orders(client, order_status=status)

    assert body["total"] == expected
    assert {item["order_status"] for item in body["items"]} == {status}


@pytest.mark.parametrize(("outcome", "expected"), OUTCOME_COUNTS.items())
async def test_outcome_filter_matches_the_golden_count(
    client: AsyncClient, outcome: str, expected: int
) -> None:
    body = await get_orders(client, delivery_outcome=outcome)

    assert body["total"] == expected
    assert body["total"] not in {LATE_INCLUDING_CANCELED, LATE_BY_TIMESTAMP}
    assert {item["delivery_outcome"] for item in body["items"]} == {outcome}


async def test_canceled_orders_with_a_delivery_date_are_never_late(
    client: AsyncClient,
) -> None:
    body = await get_orders(client, order_status="canceled", delivery_outcome="late")

    assert body["total"] == 0


async def test_the_whole_purchase_range_includes_every_order(client: AsyncClient) -> None:
    # Đơn đặt muộn nhất lúc 02:30 ngày 17/10/2018. So purchased_at <= 2018-10-17 00:00
    # sẽ đánh rơi nó và ra 99.440.
    body = await get_orders(
        client, purchased_from=FIRST_PURCHASE_DAY, purchased_to=LAST_PURCHASE_DAY
    )

    assert body["total"] == TOTAL_ORDERS


async def test_purchase_range_excludes_days_outside_it(client: AsyncClient) -> None:
    expected = sum(
        1
        for row in _csv_orders()
        if "2017-11-24" <= row["order_purchase_timestamp"][:10] <= "2017-11-25"
    )

    body = await get_orders(
        client, purchased_from="2017-11-24", purchased_to="2017-11-25"
    )

    assert body["total"] == expected
    assert all(
        "2017-11-24" <= item["purchased_at"][:10] <= "2017-11-25" for item in body["items"]
    )


async def test_delivery_range_includes_both_end_days(client: AsyncClient) -> None:
    # Viết độc lập với within_days: cắt mười ký tự ngày trên tệp CSV thay vì khoảng nửa mở.
    delivered_days = [
        row["order_delivered_customer_date"][:10]
        for row in _csv_orders()
        if row["order_delivered_customer_date"]
    ]
    expected = sum(1 for day in delivered_days if "2018-01-01" <= day <= "2018-01-31")
    last_day = sum(1 for day in delivered_days if day == "2018-01-31")
    assert last_day > 0

    whole = await get_orders(client, delivered_from="2018-01-01", delivered_to="2018-01-31")
    without_last_day = await get_orders(
        client, delivered_from="2018-01-01", delivered_to="2018-01-30"
    )

    assert whole["total"] == expected
    assert whole["total"] - without_last_day["total"] == last_day


async def test_state_filter_keeps_only_that_state(client: AsyncClient) -> None:
    states = _customer_states()
    expected = sum(
        1 for row in _csv_orders() if states.get(row["customer_id"]) == "RR"
    )

    body = await get_orders(client, customer_state="RR")

    assert body["total"] == expected
    assert {item["customer_state"] for item in body["items"]} == {"RR"}


async def test_seller_filter_counts_every_order_with_that_sellers_items(
    client: AsyncClient,
) -> None:
    seller_id = EDGE_CASE_FILTERS["busiest_seller"]
    expected = sum(
        1 for sellers in _sellers_by_order().values() if seller_id in sellers
    )

    body = await get_orders(client, seller_id=seller_id)

    assert body["total"] == expected


async def test_multi_seller_order_belongs_to_every_participating_seller(
    client: AsyncClient,
) -> None:
    order_id = EDGE_CASE_ORDERS["multi_seller"][0]
    seller_ids = sorted(_sellers_by_order()[order_id])
    assert len(seller_ids) > 1

    for seller_id in seller_ids:
        body = await get_orders(client, order_id=order_id, seller_id=seller_id)
        assert body["total"] == 1
        assert [item["order_id"] for item in body["items"]] == [order_id]


async def test_filters_combine(client: AsyncClient) -> None:
    seller_id = EDGE_CASE_FILTERS["busiest_seller"]
    states = _customer_states()
    sellers_by_order = _sellers_by_order()
    expected = sum(
        1
        for row in _csv_orders()
        if states.get(row["customer_id"]) == "SP"
        and row["order_status"] == "delivered"
        and row["order_delivered_customer_date"]
        and row["order_delivered_customer_date"][:10]
        > row["order_estimated_delivery_date"][:10]
        and "2017-01-01" <= row["order_purchase_timestamp"][:10] <= "2018-06-30"
        and seller_id in sellers_by_order.get(row["order_id"], set())
    )
    assert expected > 0

    body = await get_orders(
        client,
        seller_id=seller_id,
        customer_state="SP",
        delivery_outcome="late",
        purchased_from="2017-01-01",
        purchased_to="2018-06-30",
    )

    assert body["total"] == expected
    for item in body["items"]:
        assert item["customer_state"] == "SP"
        assert item["delivery_outcome"] == "late"
        assert "2017-01-01" <= item["purchased_at"][:10] <= "2018-06-30"


@pytest.mark.parametrize(
    "params",
    [
        {"purchased_from": "2018-01-01"},
        {"purchased_to": "2018-01-31"},
        {"delivered_from": "2018-01-01"},
        {"delivered_to": "2018-01-31"},
    ],
    ids=["only purchased_from", "only purchased_to", "only delivered_from", "only delivered_to"],
)
async def test_half_a_date_range_is_rejected_with_a_reason(
    client: AsyncClient, params: dict[str, str]
) -> None:
    response = await client.get("/orders", params=params)

    assert response.status_code == 422
    assert "must be given together" in response.json()["detail"]


@pytest.mark.parametrize(
    "params",
    [
        {"order_status": "lost"},
        {"delivery_outcome": "maybe"},
        {"purchased_from": "2018-02-30", "purchased_to": "2018-03-01"},
        {"delivered_from": "yesterday", "delivered_to": "today"},
    ],
)
async def test_invalid_filter_values_are_rejected(
    client: AsyncClient, params: dict[str, str]
) -> None:
    response = await client.get("/orders", params=params)

    assert response.status_code == 422


async def test_sellers_without_a_delivered_order_are_suggested_only_when_asked(
    client: AsyncClient, session: AsyncSession
) -> None:
    # 125 người bán chưa có đơn nào giao xong. Gợi ý của bảng điều khiển bỏ họ là đúng,
    # nhưng danh sách đơn gồm cả đơn chưa giao, nên ở đó họ phải chọn được.
    seller_id = await session.scalar(
        text(
            "SELECT s.seller_id FROM sellers s WHERE NOT EXISTS ("
            "  SELECT 1 FROM order_sellers os JOIN orders o ON o.order_id = os.order_id "
            "  WHERE os.seller_id = s.seller_id AND o.order_status = 'delivered' "
            "  AND o.delivered_to_customer_at IS NOT NULL) "
            "ORDER BY s.seller_id LIMIT 1"
        )
    )
    orders_of_seller = await get_orders(client, seller_id=seller_id)
    assert orders_of_seller["total"] > 0

    default = await client.get("/sellers", params={"q": seller_id})
    every_seller = await client.get(
        "/sellers", params={"q": seller_id, "delivered_only": "false"}
    )

    assert default.json() == []
    assert [option["seller_id"] for option in every_seller.json()] == [seller_id]
    assert every_seller.json()[0]["delivered_orders"] == 0


async def test_customer_states_cover_every_order(client: AsyncClient) -> None:
    response = await client.get("/customer-states")

    assert response.status_code == 200
    states = response.json()
    assert len(states) == 27
    assert states == sorted(states)


async def test_customer_states_require_a_session(client: AsyncClient) -> None:
    del client.headers["Authorization"]

    response = await client.get("/customer-states")

    assert response.status_code == 401
