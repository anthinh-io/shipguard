import codecs
import csv
import io
import json
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient, Response

from app.core.security import create_access_token

EDGE_CASE_FILTERS = json.loads(
    (Path(__file__).parent / "fixtures" / "edge_case_filters.json").read_text("utf-8")
)

TOTAL_ORDERS = 99_441
ORDERS_WITHOUT_ITEMS = 775
PAGE_SIZE = 50
ORDER_ID_LENGTH = 32

# Tên trường của một dòng /orders, đúng thứ tự cột trong file.
HEADER = [
    "order_id",
    "order_status",
    "delivery_outcome",
    "purchased_at",
    "estimated_delivery_date",
    "delivered_at",
    "customer_state",
    "order_value",
]

pytestmark = pytest.mark.usefixtures("derived_data")


@pytest.fixture(autouse=True)
def signed_in(client: AsyncClient) -> None:
    token = create_access_token(1, "operations_staff", [])
    client.headers["Authorization"] = f"Bearer {token}"


async def get_orders(client: AsyncClient, **params: Any) -> dict[str, Any]:
    response = await client.get("/orders", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def csv_rows(response: Response) -> list[list[str]]:
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    # Thiếu BOM thì Excel đọc UTF-8 như bảng mã cục bộ và làm vỡ dấu tiếng Việt.
    assert response.content.startswith(codecs.BOM_UTF8)
    text = response.content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(text, newline="")))


async def test_unfiltered_export_contains_every_order(client: AsyncClient) -> None:
    # Cũng là bài chứng minh session còn sống suốt lúc stream: session đóng sớm thì
    # file hỏng giữa chừng chứ không đủ 99.441 dòng. Trả 200 kèm CSV còn cho thấy
    # "export" không bị /orders/{order_id} hiểu thành một mã đơn.
    response = await client.get("/orders/export")

    rows = csv_rows(response)
    assert response.headers["content-disposition"] == 'attachment; filename="orders.csv"'
    assert rows[0] == HEADER
    data = rows[1:]
    assert len(data) == TOTAL_ORDERS
    assert all(len(row) == len(HEADER) for row in data)
    assert all(len(row[0]) == ORDER_ID_LENGTH for row in data)
    assert len({row[0] for row in data}) == TOTAL_ORDERS


@pytest.mark.parametrize(
    ("params", "min_total"),
    [
        (
            {
                "delivery_outcome": "late",
                "customer_state": "SP",
                "delivered_from": "2017-01-01",
                "delivered_to": "2018-06-30",
                "seller_id": EDGE_CASE_FILTERS["busiest_seller"],
            },
            1,
        ),
        # Bỏ người bán để danh sách trải qua nhiều trang: file phải gồm mọi trang.
        (
            {
                "delivery_outcome": "late",
                "customer_state": "SP",
                "delivered_from": "2017-01-01",
                "delivered_to": "2018-06-30",
            },
            PAGE_SIZE + 1,
        ),
    ],
    ids=["late, SP, delivery range, seller", "late, SP, delivery range"],
)
async def test_filtered_export_has_as_many_rows_as_the_list_total(
    client: AsyncClient, params: dict[str, str], min_total: int
) -> None:
    body = await get_orders(client, **params)
    assert body["total"] >= min_total

    rows = csv_rows(await client.get("/orders/export", params=params))

    data = rows[1:]
    assert len(data) == body["total"]
    assert {row[HEADER.index("customer_state")] for row in data} == {"SP"}
    assert {row[HEADER.index("delivery_outcome")] for row in data} == {"late"}


async def test_export_follows_the_list_sort_order(client: AsyncClient) -> None:
    params = {"sort": "order_value", "direction": "desc"}
    first_page = await get_orders(client, **params)

    rows = csv_rows(await client.get("/orders/export", params=params))

    data = rows[1:]
    assert [row[0] for row in data[:PAGE_SIZE]] == [
        item["order_id"] for item in first_page["items"]
    ]
    # Giá trị null ghi thành ô trống, và vẫn nằm cuối như trên danh sách.
    values = [row[HEADER.index("order_value")] for row in data]
    assert values[-ORDERS_WITHOUT_ITEMS:] == [""] * ORDERS_WITHOUT_ITEMS
    assert "" not in values[:-ORDERS_WITHOUT_ITEMS]


async def test_half_a_date_range_is_rejected_like_the_list(client: AsyncClient) -> None:
    response = await client.get("/orders/export", params={"delivered_from": "2018-01-01"})

    assert response.status_code == 422
    assert "must be given together" in response.json()["detail"]


async def test_export_requires_a_session(client: AsyncClient) -> None:
    del client.headers["Authorization"]

    response = await client.get("/orders/export")

    assert response.status_code == 401
