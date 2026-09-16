from collections import defaultdict
from decimal import Decimal

from olist_csv import read_rows
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Bộ số vàng của Order Value tính thẳng từ CSV, không đi qua câu SQL dựng bảng dẫn xuất —
# cùng một lỗi cộng sai ở hai nơi thì so với nhau vẫn xanh.


def _order_ids() -> list[str]:
    return [row["order_id"] for row in read_rows("olist_orders_dataset.csv")]


def _order_values() -> dict[str, Decimal]:
    values: dict[str, Decimal] = defaultdict(Decimal)
    for row in read_rows("olist_order_items_dataset.csv"):
        values[row["order_id"]] += Decimal(row["price"]) + Decimal(row["freight_value"])
    return values


def _payment_totals() -> dict[str, Decimal]:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for row in read_rows("olist_order_payments_dataset.csv"):
        totals[row["order_id"]] += Decimal(row["payment_value"])
    return totals


def test_golden_numbers_from_csv() -> None:
    order_ids = _order_ids()
    values = _order_values()
    payments = _payment_totals()

    assert len(order_ids) == 99_441
    assert sum(1 for order_id in order_ids if order_id not in values) == 775
    assert max(values.values()) == Decimal("13664.08")
    assert sum(1 for order_id in order_ids if order_id.lower().startswith("e481f5")) == 1

    # Chỉ so được trên đơn có cả sản phẩm lẫn thanh toán: 98.666 đơn có sản phẩm, trong
    # đó đúng một đơn không có dòng thanh toán nào, còn lại 98.665.
    comparable = [o for o in order_ids if o in values and o in payments]
    assert len(comparable) == 98_665
    # Ngưỡng hơn 1 xu, không phải so bằng tuyệt đối: trả góp chia tiền rồi làm tròn từng
    # kỳ nên lệch đúng 1 xu là chuyện thường — so bằng tuyệt đối ra 576 đơn chứ không
    # phải 303.
    mismatched = [o for o in comparable if abs(values[o] - payments[o]) > Decimal("0.01")]
    assert len(mismatched) == 303


async def test_every_order_value_matches_the_csv(session: AsyncSession) -> None:
    values = _order_values()

    rows = (await session.execute(text("SELECT order_id, order_value FROM orders"))).all()

    assert len(rows) == 99_441
    assert {row.order_id: row.order_value for row in rows} == {
        order_id: values.get(order_id) for order_id in _order_ids()
    }
