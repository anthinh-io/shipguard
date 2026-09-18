import json
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token

EDGE_CASE_ORDERS = json.loads(
    (Path(__file__).parent / "fixtures" / "edge_case_orders.json").read_text("utf-8")
)

TOTAL_ORDERS = 99_441
ORDERS_WITHOUT_ITEMS = 775
PAGE_SIZE = 50
LAST_PAGE = -(-TOTAL_ORDERS // PAGE_SIZE)

pytestmark = pytest.mark.usefixtures("derived_data")


@pytest.fixture(autouse=True)
def signed_in(client: AsyncClient) -> None:
    token = create_access_token(1, "operations_staff", [])
    client.headers["Authorization"] = f"Bearer {token}"


async def get_orders(client: AsyncClient, **params: Any) -> dict[str, Any]:
    response = await client.get("/orders", params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def only_order(client: AsyncClient, order_id: str) -> dict[str, Any]:
    body = await get_orders(client, order_id=order_id)
    assert body["total"] == 1
    return body["items"][0]


async def test_default_is_the_newest_page_of_every_order(
    client: AsyncClient, session: AsyncSession
) -> None:
    body = await get_orders(client)

    assert set(body) == {"items", "total", "page", "page_size"}
    assert body["total"] == TOTAL_ORDERS
    assert body["page"] == 1
    assert body["page_size"] == PAGE_SIZE
    assert len(body["items"]) == PAGE_SIZE
    assert set(body["items"][0]) == {
        "order_id",
        "order_status",
        "delivery_outcome",
        "purchased_at",
        "estimated_delivery_date",
        "delivered_at",
        "customer_state",
        "order_value",
        "risk_level",
    }
    newest = await session.scalar(text("SELECT max(purchased_at) FROM orders"))
    assert body["items"][0]["purchased_at"] == newest.isoformat()


@pytest.mark.parametrize("prefix", ["e481f5", "E481F5", "  e481f5  "])
async def test_order_id_prefix_matches_regardless_of_case(
    client: AsyncClient, prefix: str
) -> None:
    body = await get_orders(client, order_id=prefix)

    assert body["total"] == 1
    assert body["items"][0]["order_id"].startswith("e481f5")


@pytest.mark.parametrize("prefix", ["%", "_", "e481f_"])
async def test_wildcards_in_the_search_are_literal_characters(
    client: AsyncClient, prefix: str
) -> None:
    # Không mã đơn nào chứa "%" hay "_". Không thoát ký tự thì "%" khớp cả 99.441 đơn,
    # còn "e481f_" khớp như "e481f5".
    body = await get_orders(client, order_id=prefix)

    assert body["total"] == 0
    assert body["items"] == []


async def test_blank_search_does_not_filter(client: AsyncClient) -> None:
    body = await get_orders(client, order_id="   ")

    assert body["total"] == TOTAL_ORDERS


@pytest.mark.parametrize(
    ("sort", "column"),
    [
        ("purchased_at", "purchased_at"),
        ("estimated_delivery_date", "estimated_delivery_date"),
        ("delivered_at", "delivered_to_customer_at"),
    ],
)
@pytest.mark.parametrize(("direction", "aggregate"), [("asc", "min"), ("desc", "max")])
async def test_date_sorts_start_from_the_extreme_value(
    client: AsyncClient,
    session: AsyncSession,
    sort: str,
    column: str,
    direction: str,
    aggregate: str,
) -> None:
    body = await get_orders(client, sort=sort, direction=direction)

    # Ngày giao có đơn trống; Postgres mặc định đưa NULL lên đầu khi giảm dần, nên dòng
    # đầu khớp max() chứng tỏ đơn chưa giao đã bị đẩy xuống cuối.
    expected = await session.scalar(text(f"SELECT {aggregate}({column}) FROM orders"))
    assert body["items"][0][sort] == expected.isoformat()


async def test_most_valuable_order_comes_first_when_sorting_by_value(
    client: AsyncClient,
) -> None:
    body = await get_orders(client, sort="order_value", direction="desc")

    assert body["items"][0]["order_value"] == 13664.08


@pytest.mark.parametrize("direction", ["asc", "desc"])
async def test_orders_without_a_value_are_always_last(
    client: AsyncClient, direction: str
) -> None:
    last_valued_position = TOTAL_ORDERS - ORDERS_WITHOUT_ITEMS  # đếm từ 1
    boundary_page = -(-last_valued_position // PAGE_SIZE)
    boundary_index = (last_valued_position - 1) % PAGE_SIZE

    boundary = await get_orders(
        client, sort="order_value", direction=direction, page=boundary_page
    )
    last = await get_orders(
        client, sort="order_value", direction=direction, page=LAST_PAGE
    )

    values = [item["order_value"] for item in boundary["items"]]
    assert all(value is not None for value in values[: boundary_index + 1])
    assert all(value is None for value in values[boundary_index + 1 :])
    assert len(last["items"]) == TOTAL_ORDERS - (LAST_PAGE - 1) * PAGE_SIZE
    assert all(item["order_value"] is None for item in last["items"])


async def test_jumping_to_a_page_returns_that_slice(
    client: AsyncClient, session: AsyncSession
) -> None:
    body = await get_orders(client, page=1000)

    expected = (
        await session.scalars(
            text(
                "SELECT order_id FROM orders "
                "ORDER BY purchased_at DESC, order_id LIMIT 50 OFFSET 49950"
            )
        )
    ).all()
    assert body["page"] == 1000
    assert body["total"] == TOTAL_ORDERS
    assert [item["order_id"] for item in body["items"]] == expected


async def test_ties_are_broken_by_order_id_so_pages_are_stable(
    client: AsyncClient, session: AsyncSession
) -> None:
    # Hàng trăm đơn trùng một ngày cam kết. Thiếu khoá phụ thì thứ tự trong nhóm trùng
    # tuỳ kế hoạch truy vấn, và hai trang liền nhau có thể trả lẫn đơn của nhau.
    tied_on_page = await session.scalar(
        text(
            "SELECT count(DISTINCT estimated_delivery_date) FROM ("
            "SELECT estimated_delivery_date FROM orders "
            "ORDER BY estimated_delivery_date, order_id LIMIT 50 OFFSET 49950) page"
        )
    )
    assert tied_on_page < PAGE_SIZE

    body = await get_orders(
        client, sort="estimated_delivery_date", direction="asc", page=1000
    )

    expected = (
        await session.scalars(
            text(
                "SELECT order_id FROM orders "
                "ORDER BY estimated_delivery_date, order_id LIMIT 50 OFFSET 49950"
            )
        )
    ).all()
    assert [item["order_id"] for item in body["items"]] == expected


async def test_a_page_past_the_end_is_empty_but_keeps_the_total(
    client: AsyncClient,
) -> None:
    body = await get_orders(client, page=LAST_PAGE + 1)

    assert body["items"] == []
    assert body["total"] == TOTAL_ORDERS


async def test_canceled_orders_with_a_delivery_date_have_no_outcome(
    client: AsyncClient, session: AsyncSession
) -> None:
    order_ids = (
        await session.scalars(
            text(
                "SELECT order_id FROM orders "
                "WHERE order_status = 'canceled' AND delivered_to_customer_at IS NOT NULL"
            )
        )
    ).all()
    assert len(order_ids) == 6

    for order_id in order_ids:
        item = await only_order(client, order_id)
        assert item["delivered_at"] is not None
        assert item["delivery_outcome"] == "no_outcome"


async def test_an_overdue_order_still_in_transit_has_no_outcome(
    client: AsyncClient, session: AsyncSession
) -> None:
    order_id = await session.scalar(
        text(
            "SELECT order_id FROM orders WHERE order_status = 'shipped' "
            "AND delivered_to_customer_at IS NULL "
            "AND estimated_delivery_date < '2018-01-01' LIMIT 1"
        )
    )

    item = await only_order(client, order_id)

    assert item["delivered_at"] is None
    assert item["delivery_outcome"] == "no_outcome"


async def test_delivered_orders_are_late_or_on_time(
    client: AsyncClient, session: AsyncSession
) -> None:
    late_id = await session.scalar(
        text("SELECT order_id FROM orders WHERE order_status = 'delivered' AND is_late LIMIT 1")
    )
    # Giao đúng ngày cam kết, dù muộn giờ, vẫn là đúng hạn.
    on_time_id = EDGE_CASE_ORDERS["delivered_on_estimated_date"][0]

    assert (await only_order(client, late_id))["delivery_outcome"] == "late"
    assert (await only_order(client, on_time_id))["delivery_outcome"] == "on_time"


@pytest.mark.parametrize(
    "params",
    [
        {"sort": "customer_state"},
        {"direction": "up"},
        {"page": 0},
        # OFFSET là bigint: trang lớn cỡ này tràn số trong Postgres và thành lỗi 500.
        {"page": "100000000000000000000"},
    ],
)
async def test_invalid_parameters_are_rejected(
    client: AsyncClient, params: dict[str, Any]
) -> None:
    response = await client.get("/orders", params=params)

    assert response.status_code == 422


@pytest.mark.parametrize("authorization", [None, "Bearer not-a-jwt"])
async def test_orders_require_a_session(
    client: AsyncClient, authorization: str | None
) -> None:
    del client.headers["Authorization"]
    headers = {} if authorization is None else {"Authorization": authorization}

    response = await client.get("/orders", headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
