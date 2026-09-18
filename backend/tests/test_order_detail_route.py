import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from olist_csv import read_rows
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.services.orders import get_order_detail

FIXTURES = Path(__file__).parent / "fixtures"
EDGE_CASE_ORDERS = json.loads((FIXTURES / "edge_case_orders.json").read_text("utf-8"))
# Đơn mẫu ghim sẵn thay cho truy vấn quét bảng thô để tìm chúng. Chỉ ghim MÃ ĐƠN, không
# ghim giá trị kỳ vọng: giá trị kỳ vọng luôn đọc từ CSV, nếu không nó lại được sinh ra từ
# chính lớp dẫn xuất đang bị kiểm. Công thức dựng lại nằm trong backend/README.md.
EDGE_CASE_FILTERS = json.loads((FIXTURES / "edge_case_filters.json").read_text("utf-8"))


def _csv_categories(order_id: str) -> set[str | None]:
    """Nhãn danh mục mà trang chi tiết phải hiện cho một đơn, tính thẳng từ CSV.

    Nhãn tiếng Anh khi có bản dịch, tên gốc khi chưa dịch, rỗng khi sản phẩm không
    thuộc danh mục nào — đúng ba nhánh của phép coalesce ở đường đọc.
    """
    original = {
        row["product_id"]: row["product_category_name"]
        for row in read_rows("olist_products_dataset.csv")
    }
    english = {
        row["product_category_name"]: row["product_category_name_english"]
        for row in read_rows("product_category_name_translation.csv")
    }
    labels: set[str | None] = set()
    for row in read_rows("olist_order_items_dataset.csv"):
        if row["order_id"] != order_id:
            continue
        name = original.get(row["product_id"]) or None
        labels.add(english.get(name, name) if name else None)
    return labels

pytestmark = pytest.mark.usefixtures("derived_data")


@pytest.fixture(autouse=True)
def signed_in(client: AsyncClient) -> None:
    token = create_access_token(1, "operations_staff", [])
    client.headers["Authorization"] = f"Bearer {token}"


async def get_detail(client: AsyncClient, order_id: str) -> dict[str, Any]:
    response = await client.get(f"/orders/{order_id}")
    assert response.status_code == 200, response.text
    return response.json()


async def test_a_late_multi_seller_order_shows_every_part_of_the_order(
    client: AsyncClient, session: AsyncSession
) -> None:
    order_id = await session.scalar(
        text(
            "SELECT o.order_id FROM orders o "
            "WHERE o.order_status = 'delivered' AND o.is_late "
            "AND (SELECT count(*) FROM order_sellers s WHERE s.order_id = o.order_id) > 1 "
            "ORDER BY o.order_id LIMIT 1"
        )
    )

    body = await get_detail(client, order_id)

    assert set(body) == {
        "order_id",
        "order_status",
        "delivery_outcome",
        "order_value",
        "timeline",
        "address",
        "items",
        "sellers",
        "payments",
        "reviews",
        "next_milestone",
        "cancelable",
    }
    assert body["order_id"] == order_id
    assert body["order_status"] == "delivered"
    assert body["delivery_outcome"] == "late"
    assert set(body["timeline"]) == {
        "purchased_at",
        "payment_approved_at",
        "handed_to_carrier_at",
        "delivered_at",
        "estimated_delivery_date",
        "payment_approval_days",
        "seller_handling_days",
        "carrier_transit_days",
    }
    assert body["timeline"]["delivered_at"][:10] > body["timeline"]["estimated_delivery_date"]

    # Đi qua Decimal rồi mới sang float, không ép thẳng chuỗi CSV: Order Value cộng dồn
    # bằng số thực đã từng trôi xu một lần rồi.
    csv_items = sorted(
        (
            row
            for row in read_rows("olist_order_items_dataset.csv")
            if row["order_id"] == order_id
        ),
        key=lambda row: int(row["order_item_id"]),
    )
    assert [
        (item["order_item_id"], item["seller_id"], item["price"], item["freight_value"])
        for item in body["items"]
    ] == [
        (
            int(row["order_item_id"]),
            row["seller_id"],
            float(Decimal(row["price"])),
            float(Decimal(row["freight_value"])),
        )
        for row in csv_items
    ]
    assert set(body["items"][0]) == {
        "order_item_id",
        "product_id",
        "category",
        "price",
        "freight_value",
        "seller_id",
    }

    seller_ids = {item["seller_id"] for item in body["items"]}
    assert len(seller_ids) > 1
    assert {seller["seller_id"] for seller in body["sellers"]} == seller_ids
    assert all(seller["seller_city"] and seller["seller_state"] for seller in body["sellers"])


async def test_stage_durations_are_read_from_the_generated_columns(
    client: AsyncClient, session: AsyncSession
) -> None:
    order_id = "e481f51cbdc54678b7cc49136f2d6af7"
    row = (
        await session.execute(
            text(
                "SELECT extract(epoch FROM payment_approval) / 86400 AS pa, "
                "extract(epoch FROM seller_handling) / 86400 AS sh, "
                "extract(epoch FROM carrier_transit) / 86400 AS ct "
                "FROM orders WHERE order_id = :order"
            ),
            {"order": order_id},
        )
    ).one()

    timeline = (await get_detail(client, order_id))["timeline"]

    assert timeline["payment_approval_days"] == pytest.approx(float(row.pa))
    assert timeline["seller_handling_days"] == pytest.approx(float(row.sh))
    assert timeline["carrier_transit_days"] == pytest.approx(float(row.ct))


async def test_categories_are_english_with_the_original_name_as_fallback(
    client: AsyncClient,
) -> None:
    # Ba đơn mẫu ghim sẵn, mỗi đơn một trường hợp: có bản dịch, có danh mục nhưng chưa
    # dịch, và không danh mục nào. So trọn bộ nhãn chứ không chỉ đòi có mặt một nhãn —
    # trang hiện thừa một danh mục lạ thì phép so lỏng vẫn xanh.
    for key in (
        "translated_category_order",
        "untranslated_category_order",
        "uncategorized_order",
    ):
        order_id = EDGE_CASE_FILTERS[key]
        items = (await get_detail(client, order_id))["items"]

        assert {item["category"] for item in items} == _csv_categories(order_id)


async def test_missing_milestones_are_null_and_the_rest_is_intact(
    client: AsyncClient,
) -> None:
    for order_id in EDGE_CASE_ORDERS["missing_intermediate_milestone"]:
        body = await get_detail(client, order_id)
        timeline = body["timeline"]

        assert timeline["purchased_at"] is not None
        assert timeline["delivered_at"] is not None
        if timeline["payment_approved_at"] is None:
            assert timeline["payment_approval_days"] is None
            assert timeline["seller_handling_days"] is None
        if timeline["handed_to_carrier_at"] is None:
            assert timeline["seller_handling_days"] is None
            assert timeline["carrier_transit_days"] is None
        assert body["items"]
        assert body["address"]["customer_city"]


async def test_an_undelivered_order_has_no_delivery_date_and_no_outcome(
    client: AsyncClient, session: AsyncSession
) -> None:
    order_id = await session.scalar(
        text(
            "SELECT order_id FROM orders WHERE order_status = 'created' ORDER BY order_id LIMIT 1"
        )
    )

    body = await get_detail(client, order_id)

    assert body["delivery_outcome"] == "no_outcome"
    assert body["timeline"]["delivered_at"] is None
    assert body["timeline"]["carrier_transit_days"] is None


async def test_an_order_without_a_review_has_an_empty_review_list(
    client: AsyncClient,
) -> None:
    body = await get_detail(client, EDGE_CASE_ORDERS["no_review"][0])

    assert body["reviews"] == []


async def test_reviews_carry_the_score_and_comment(client: AsyncClient) -> None:
    # Mã đơn ghim sẵn, nhưng điểm và nội dung kỳ vọng đọc từ CSV: đó là phép đối chiếu
    # thật, không phải chuyện chọn đơn mẫu.
    order_id = EDGE_CASE_FILTERS["commented_review_order"]
    row = next(
        r
        for r in read_rows("olist_order_reviews_dataset.csv")
        if r["order_id"] == order_id and r["review_comment_message"]
    )

    reviews = (await get_detail(client, order_id))["reviews"]

    assert {
        "review_score": int(row["review_score"]),
        "comment_message": row["review_comment_message"],
    }.items() <= reviews[0].items()
    assert set(reviews[0]) == {"review_score", "comment_title", "comment_message", "created_at"}


async def test_multiple_reviews_come_back_oldest_first_in_a_stable_order(
    client: AsyncClient, session: AsyncSession
) -> None:
    # 547 đơn có nhiều hơn một đánh giá. Trước đây thứ tự đọc bất định ở 157 cặp trùng
    # thời điểm tạo; giờ nó được đóng cứng lúc dựng bằng review_sequential.
    order_id = await session.scalar(
        text(
            "SELECT order_id FROM order_reviews GROUP BY order_id "
            "HAVING count(*) > 1 ORDER BY order_id LIMIT 1"
        )
    )

    reviews = (await get_detail(client, order_id))["reviews"]

    assert len(reviews) > 1
    assert [r["created_at"] for r in reviews] == sorted(r["created_at"] for r in reviews)


async def test_an_order_without_items_has_no_items_sellers_or_value(
    client: AsyncClient, session: AsyncSession
) -> None:
    order_id = await session.scalar(
        text("SELECT order_id FROM orders WHERE order_value IS NULL ORDER BY order_id LIMIT 1")
    )

    body = await get_detail(client, order_id)

    assert body["items"] == []
    assert body["sellers"] == []
    assert body["order_value"] is None


async def test_payments_are_listed_in_sequence_with_installments(
    client: AsyncClient,
) -> None:
    order_id = EDGE_CASE_FILTERS["multi_payment_order"]

    payments = (await get_detail(client, order_id))["payments"]

    assert len(payments) > 1
    sequence = [payment["payment_sequential"] for payment in payments]
    assert sequence == sorted(sequence)
    assert set(payments[0]) == {
        "payment_sequential",
        "payment_type",
        "payment_installments",
        "payment_value",
    }
    assert all(isinstance(payment["payment_value"], float) for payment in payments)


async def test_the_shipping_address_has_city_state_and_a_five_digit_zip_prefix(
    client: AsyncClient,
) -> None:
    # Đơn có mã bưu chính bắt đầu bằng số 0 — chỗ duy nhất phép đệm lại 5 chữ số nói lên
    # điều gì. So thẳng chuỗi trong CSV chứ không định dạng lại: đúng thứ tệp gốc ghi là
    # đúng thứ trang phải hiện.
    order_id = EDGE_CASE_FILTERS["leading_zero_zip_order"]
    customers = {
        row["customer_id"]: row for row in read_rows("olist_customers_dataset.csv")
    }
    order = next(
        row
        for row in read_rows("olist_orders_dataset.csv")
        if row["order_id"] == order_id
    )
    customer = customers[order["customer_id"]]
    assert customer["customer_zip_code_prefix"].startswith("0")

    address = (await get_detail(client, order_id))["address"]

    assert address == {
        "customer_city": customer["customer_city"],
        "customer_state": customer["customer_state"],
        "customer_zip_code_prefix": customer["customer_zip_code_prefix"],
    }


async def test_detail_still_opens_before_the_derived_tables_are_rebuilt(
    session: AsyncSession,
) -> None:
    # Migration 0007 thêm hai cột cho phép NULL; tới lúc chạy lại build_derived_data thì
    # chúng trống. Trang chi tiết phải mở được chứ không trả 500 cho mọi đơn.
    #
    # Gọi thẳng service trong cùng một giao dịch rồi rollback, không commit: bảng dẫn xuất
    # dùng chung cả phiên test, và một lần chạy bị ngắt giữa chừng không được để lại đơn
    # thiếu địa chỉ cho test khác.
    order_id = "e481f51cbdc54678b7cc49136f2d6af7"
    await session.execute(
        text(
            "UPDATE orders SET customer_city = NULL, customer_zip_code_prefix = NULL "
            "WHERE order_id = :order"
        ),
        {"order": order_id},
    )
    try:
        detail = await get_order_detail(session, order_id)
    finally:
        await session.rollback()

    assert detail is not None
    address = detail.address.model_dump()
    assert address["customer_city"] is None
    assert address["customer_zip_code_prefix"] is None
    assert address["customer_state"]


async def test_an_unknown_order_is_not_found(client: AsyncClient) -> None:
    response = await client.get("/orders/00000000000000000000000000000000")

    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found"


@pytest.mark.parametrize("authorization", [None, "Bearer not-a-jwt"])
async def test_order_detail_requires_a_session(
    client: AsyncClient, authorization: str | None
) -> None:
    del client.headers["Authorization"]
    headers = {} if authorization is None else {"Authorization": authorization}

    response = await client.get("/orders/e481f51cbdc54678b7cc49136f2d6af7", headers=headers)

    assert response.status_code == 401
