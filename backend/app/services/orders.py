from datetime import date, datetime
from typing import Literal

import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.derived import orders
from app.services.queries import DELIVERED, like_prefix, sold_by, within_days

PAGE_SIZE = 50

OrderSort = Literal["purchased_at", "estimated_delivery_date", "delivered_at", "order_value"]
SortDirection = Literal["asc", "desc"]

# Order Status theo CONTEXT.md: đúng tám giá trị sàn ghi nhận.
OrderStatus = Literal[
    "created",
    "approved",
    "invoiced",
    "processing",
    "shipped",
    "delivered",
    "canceled",
    "unavailable",
]

# Delivery Outcome theo CONTEXT.md. Chỉ Delivered Order mới đúng hạn hay trễ; đơn đã hủy
# lỡ có ngày giao, hay đơn quá hạn còn trên đường, đều chưa có kết quả. Không so với
# "hôm nay" — dữ liệu là lịch sử.
DeliveryOutcome = Literal["on_time", "late", "no_outcome"]

# Cùng định nghĩa với _delivery_outcome, viết thành điều kiện WHERE. Phải dựng trên
# DELIVERED chứ không trên is_late một mình: 6 đơn đã hủy có ngày giao cũng có is_late,
# một trong số đó trễ, và bỏ DELIVERED thì bộ lọc "trễ" ra 6.535 thay vì 6.534.
# not_(DELIVERED) không vướng logic ba giá trị: order_status NOT NULL và IS NOT NULL
# không bao giờ ra NULL.
OUTCOME_PREDICATES: dict[DeliveryOutcome, sa.ColumnElement[bool]] = {
    "on_time": sa.and_(DELIVERED, orders.c.is_late.is_not(True)),
    "late": sa.and_(DELIVERED, orders.c.is_late.is_(True)),
    "no_outcome": sa.not_(DELIVERED),
}

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


class OrderFilters(BaseModel):
    # None ở mỗi trường nghĩa là không lọc theo chiều đó. Hai khoảng ngày là cặp
    # (ngày đầu, ngày cuối), tính cả hai đầu; route đã chặn trường hợp chỉ có một đầu.
    order_id_prefix: str = ""
    order_status: OrderStatus | None = None
    delivery_outcome: DeliveryOutcome | None = None
    purchased: tuple[date, date] | None = None
    delivered: tuple[date, date] | None = None
    customer_state: str | None = None
    seller_id: str | None = None


def _where(filters: OrderFilters) -> list[sa.ColumnElement[bool]]:
    clauses: list[sa.ColumnElement[bool]] = []
    if filters.order_id_prefix.strip():
        # Viết đúng dạng lower(order_id) LIKE để khớp chỉ mục ix_orders_order_id_prefix;
        # ILIKE cho cùng kết quả nhưng quét cả bảng.
        pattern = like_prefix(filters.order_id_prefix.strip().lower())
        clauses.append(sa.func.lower(orders.c.order_id).like(pattern, escape="\\"))
    if filters.order_status is not None:
        clauses.append(orders.c.order_status == filters.order_status)
    if filters.delivery_outcome is not None:
        clauses.append(OUTCOME_PREDICATES[filters.delivery_outcome])
    # Purchase Date là mốc mặc định khi tra đơn; ngày giao là bộ lọc riêng, độc lập.
    if filters.purchased is not None:
        clauses.append(within_days(orders.c.purchased_at, *filters.purchased))
    if filters.delivered is not None:
        clauses.append(within_days(orders.c.delivered_to_customer_at, *filters.delivered))
    if filters.customer_state is not None:
        clauses.append(orders.c.customer_state == filters.customer_state)
    if filters.seller_id is not None:
        clauses.append(sold_by(filters.seller_id))
    return clauses


async def list_orders(
    session: AsyncSession,
    filters: OrderFilters,
    *,
    sort: OrderSort,
    direction: SortDirection,
    page: int,
) -> OrderList:
    """Một trang danh sách đơn khớp mọi điều kiện trong `filters` cùng lúc."""
    where = _where(filters)

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


async def list_customer_states(session: AsyncSession) -> list[str]:
    """Mọi bang có đơn, không áp bộ lọc nào.

    Khác list_customer_states của bảng điều khiển, vốn chỉ đếm đơn đã giao: danh sách đơn
    gồm cả đơn chưa giao, nên một bang chỉ có đơn đang trên đường vẫn phải chọn được.
    """
    rows = await session.scalars(
        sa.select(orders.c.customer_state).distinct().order_by(orders.c.customer_state)
    )
    return list(rows.all())
