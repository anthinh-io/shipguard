import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.scripts.load_raw_data import CSV_DIR

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


def _csv_orders() -> list[dict[str, str]]:
    with open(CSV_DIR / "olist_orders_dataset.csv", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


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


async def test_purchase_range_excludes_days_outside_it(
    client: AsyncClient, session: AsyncSession
) -> None:
    expected = await session.scalar(
        text(
            "SELECT count(*) FROM raw_orders "
            "WHERE order_purchase_timestamp::date BETWEEN '2017-11-24' AND '2017-11-25'"
        )
    )

    body = await get_orders(
        client, purchased_from="2017-11-24", purchased_to="2017-11-25"
    )

    assert body["total"] == expected
    assert all(
        "2017-11-24" <= item["purchased_at"][:10] <= "2017-11-25" for item in body["items"]
    )


async def test_delivery_range_includes_both_end_days(
    client: AsyncClient, session: AsyncSession
) -> None:
    # Viết độc lập với within_days: ép ::date trên bảng thô thay vì khoảng nửa mở.
    expected = await session.scalar(
        text(
            "SELECT count(*) FROM raw_orders "
            "WHERE order_delivered_customer_date::date BETWEEN '2018-01-01' AND '2018-01-31'"
        )
    )
    last_day = await session.scalar(
        text(
            "SELECT count(*) FROM raw_orders "
            "WHERE order_delivered_customer_date::date = '2018-01-31'"
        )
    )
    assert last_day > 0

    whole = await get_orders(client, delivered_from="2018-01-01", delivered_to="2018-01-31")
    without_last_day = await get_orders(
        client, delivered_from="2018-01-01", delivered_to="2018-01-30"
    )

    assert whole["total"] == expected
    assert whole["total"] - without_last_day["total"] == last_day


async def test_state_filter_keeps_only_that_state(
    client: AsyncClient, session: AsyncSession
) -> None:
    expected = await session.scalar(
        text(
            "SELECT count(*) FROM raw_orders o "
            "JOIN raw_customers c ON c.customer_id = o.customer_id "
            "WHERE c.customer_state = 'RR'"
        )
    )

    body = await get_orders(client, customer_state="RR")

    assert body["total"] == expected
    assert {item["customer_state"] for item in body["items"]} == {"RR"}


async def test_seller_filter_counts_every_order_with_that_sellers_items(
    client: AsyncClient, session: AsyncSession
) -> None:
    seller_id = EDGE_CASE_FILTERS["busiest_seller"]
    expected = await session.scalar(
        text(
            "SELECT count(DISTINCT order_id) FROM raw_order_items WHERE seller_id = :seller"
        ),
        {"seller": seller_id},
    )

    body = await get_orders(client, seller_id=seller_id)

    assert body["total"] == expected


async def test_multi_seller_order_belongs_to_every_participating_seller(
    client: AsyncClient, session: AsyncSession
) -> None:
    order_id = EDGE_CASE_ORDERS["multi_seller"][0]
    seller_ids = (
        await session.scalars(
            text(
                "SELECT DISTINCT seller_id FROM raw_order_items WHERE order_id = :order"
            ),
            {"order": order_id},
        )
    ).all()
    assert len(seller_ids) > 1

    for seller_id in seller_ids:
        body = await get_orders(client, order_id=order_id, seller_id=seller_id)
        assert body["total"] == 1
        assert [item["order_id"] for item in body["items"]] == [order_id]


async def test_filters_combine(client: AsyncClient, session: AsyncSession) -> None:
    seller_id = EDGE_CASE_FILTERS["busiest_seller"]
    expected = await session.scalar(
        text(
            "SELECT count(*) FROM raw_orders o "
            "JOIN raw_customers c ON c.customer_id = o.customer_id "
            "WHERE c.customer_state = 'SP' "
            "AND o.order_status = 'delivered' "
            "AND o.order_delivered_customer_date IS NOT NULL "
            "AND o.order_delivered_customer_date::date "
            "    > o.order_estimated_delivery_date::date "
            "AND o.order_purchase_timestamp::date BETWEEN '2017-01-01' AND '2018-06-30' "
            "AND EXISTS (SELECT 1 FROM raw_order_items i "
            "            WHERE i.order_id = o.order_id AND i.seller_id = :seller)"
        ),
        {"seller": seller_id},
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
