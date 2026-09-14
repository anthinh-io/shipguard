from datetime import date, datetime
from typing import Literal

import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.derived import orders
from app.services.queries import DELIVERED, like_prefix

PAGE_SIZE = 50

OrderSort = Literal["purchased_at", "estimated_delivery_date", "delivered_at", "order_value"]
SortDirection = Literal["asc", "desc"]

# Delivery Outcome theo CONTEXT.md. Chỉ Delivered Order mới đúng hạn hay trễ; đơn đã hủy
# lỡ có ngày giao, hay đơn quá hạn còn trên đường, đều chưa có kết quả. Không so với
# "hôm nay" — dữ liệu là lịch sử.
DeliveryOutcome = Literal["on_time", "late", "no_outcome"]

SORT_COLUMNS: dict[OrderSort, sa.Column[object]] = {
    "purchased_at": orders.c.purchased_at,
    "estimated_delivery_date": orders.c.estimated_delivery_date,
    "delivered_at": orders.c.delivered_to_customer_at,
    "order_value": orders.c.order_value,
}


class OrderListItem(BaseModel):
    order_id: str
    order_status: str
    delivery_outcome: DeliveryOutcome
    purchased_at: datetime
    estimated_delivery_date: date
    delivered_at: datetime | None
    customer_state: str
    order_value: float | None


class OrderList(BaseModel):
    items: list[OrderListItem]
    total: int
    page: int
    page_size: int


async def list_orders(
    session: AsyncSession,
    *,
    order_id: str,
    sort: OrderSort,
    direction: SortDirection,
    page: int,
) -> OrderList:
    """Một trang danh sách đơn, lọc theo tiền tố mã đơn nếu có."""
    where: list[sa.ColumnElement[bool]] = []
    if order_id.strip():
        # Viết đúng dạng lower(order_id) LIKE để khớp chỉ mục ix_orders_order_id_prefix;
        # ILIKE cho cùng kết quả nhưng quét cả bảng.
        pattern = like_prefix(order_id.strip().lower())
        where.append(sa.func.lower(orders.c.order_id).like(pattern, escape="\\"))

    total = await session.scalar(sa.select(sa.func.count()).select_from(orders).where(*where))

    column = SORT_COLUMNS[sort]
    ordering = column.asc() if direction == "asc" else column.desc()
    # Ô trống luôn nằm cuối ở cả hai chiều: đơn chưa giao hay không có sản phẩm không
    # phải là "nhỏ nhất" hay "lớn nhất". Chỉ gắn cho cột cho phép NULL — trên purchased_at,
    # DESC NULLS LAST khiến Postgres bỏ chỉ mục và sắp cả bảng cho trang mặc định.
    if column.nullable:
        ordering = ordering.nulls_last()
    rows = (
        await session.execute(
            sa.select(
                orders.c.order_id,
                orders.c.order_status,
                orders.c.purchased_at,
                orders.c.estimated_delivery_date,
                orders.c.delivered_to_customer_at,
                orders.c.customer_state,
                orders.c.order_value,
                orders.c.is_late,
                DELIVERED.label("is_delivered"),
            )
            .where(*where)
            # order_id phá hoà để lật trang không trả trùng hay bỏ sót đơn.
            .order_by(ordering, orders.c.order_id)
            .limit(PAGE_SIZE)
            .offset((page - 1) * PAGE_SIZE)
        )
    ).all()

    return OrderList(
        items=[
            OrderListItem(
                order_id=row.order_id,
                order_status=row.order_status,
                delivery_outcome=_delivery_outcome(row.is_delivered, row.is_late),
                purchased_at=row.purchased_at,
                estimated_delivery_date=row.estimated_delivery_date,
                delivered_at=row.delivered_to_customer_at,
                customer_state=row.customer_state,
                order_value=row.order_value,
            )
            for row in rows
        ],
        total=total or 0,
        page=page,
        page_size=PAGE_SIZE,
    )


def _delivery_outcome(is_delivered: bool, is_late: bool | None) -> DeliveryOutcome:
    if not is_delivered:
        return "no_outcome"
    return "late" if is_late else "on_time"
