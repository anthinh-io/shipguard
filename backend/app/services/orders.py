import csv
import io
from collections.abc import AsyncIterator
from datetime import date, datetime
from typing import Literal

import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.derived import (
    order_items,
    order_payments,
    order_reviews,
    order_sellers,
    orders,
    product_categories,
    sellers,
)
from app.models.risk import risk_assessments
from app.services.order_milestones import Milestone, is_cancelable, next_milestone
from app.services.queries import DELIVERED, like_prefix, sold_by, within_days

PAGE_SIZE = 50
# Số dòng mỗi lần đọc từ con trỏ khi xuất CSV, cũng là số dòng mỗi mảnh gửi đi.
EXPORT_BATCH = 1000

OrderSort = Literal["purchased_at", "estimated_delivery_date", "delivered_at", "order_value"]
SortDirection = Literal["asc", "desc"]

# Risk Level và trạng thái xử lý (#36) đều tính trên lần đánh giá MỚI NHẤT của đơn — cùng
# tiêu chí phá thế hoà (assessed_at DESC, id DESC) với list_risk_assessments/
# _superseded_clause trong risk_assessments.py. Không tái dùng thẳng hai hàm đó: import
# ngược từ đây sang risk_assessments.py sẽ khép vòng (xem chú thích đầu risk_assessments.py).
RiskLevel = Literal["high", "low", "not_assessed"]
HandlingStatus = Literal["unhandled", "handled"]

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
    # Cột duy nhất cần thêm cho #36: field mới ở đây tự thành cột CSV qua
    # export_orders_csv (đọc model_fields), không cần sửa gì thêm ở đó.
    risk_level: RiskLevel


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
    risk_level: RiskLevel | None = None
    handling_status: HandlingStatus | None = None


# Lần đánh giá mới nhất của mỗi đơn, tối đa một dòng — LATERAL chứ không JOIN thường: JOIN
# thường nhân dòng với đơn có nhiều lần đánh giá, làm sai cả total lẫn số dòng trả về, cùng
# cạm bẫy sold_by đã cảnh báo ở queries.py. LATERAL là bắt buộc chứ không phải lựa chọn:
# subquery tương quan tới orders.c.order_id (một FROM khác trong cùng câu lệnh) chỉ hợp lệ
# trên Postgres khi có từ khoá LATERAL.
_latest_assessment = (
    sa.select(
        risk_assessments.c.is_high_risk,
        risk_assessments.c.intervention,
    )
    .where(risk_assessments.c.order_id == orders.c.order_id)
    .order_by(risk_assessments.c.assessed_at.desc(), risk_assessments.c.id.desc())
    .limit(1)
    .lateral("latest_assessment")
)

# FROM dùng chung bởi list_orders (câu đếm) và _list_statement (câu chọn dòng) — hai câu
# phải cùng một FROM/JOIN, không thì total và items lệch nhau khi risk_level/handling_status
# tham gia lọc.
_ORDERS_WITH_LATEST_ASSESSMENT = orders.outerjoin(_latest_assessment, sa.true())

# is_high_risk là NOT NULL trên risk_assessments, nên NULL ở đây chỉ có thể do LEFT JOIN
# không khớp dòng nào — tức đơn chưa từng được đánh giá.
_RISK_LEVEL = sa.case(
    (_latest_assessment.c.is_high_risk.is_(None), "not_assessed"),
    (_latest_assessment.c.is_high_risk.is_(True), "high"),
    else_="low",
)

# Đúng định nghĩa needs_handling của list_risk_assessments (risk_assessments.py): lần đánh
# giá mới nhất, chưa có Intervention, đơn chưa hủy. Chỉ nhánh "chưa xử lý" loại đơn đã hủy —
# "đã xử lý" thì không, một Intervention đã ghi vẫn là đã ghi dù đơn sau đó bị hủy.
_IS_UNHANDLED = sa.and_(
    _latest_assessment.c.is_high_risk.is_not(None),
    _latest_assessment.c.intervention.is_(None),
    orders.c.order_status != "canceled",
)

_IS_HANDLED = _latest_assessment.c.intervention.is_not(None)


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
    if filters.risk_level is not None:
        clauses.append(_RISK_LEVEL == filters.risk_level)
    if filters.handling_status is not None:
        clauses.append(_IS_UNHANDLED if filters.handling_status == "unhandled" else _IS_HANDLED)
    return clauses


def _list_statement(
    filters: OrderFilters, sort: OrderSort, direction: SortDirection
) -> sa.Select:
    column = SORT_COLUMNS[sort]
    ordering = column.asc() if direction == "asc" else column.desc()
    # Ô trống luôn nằm cuối ở cả hai chiều: đơn chưa giao hay không có sản phẩm không
    # phải là "nhỏ nhất" hay "lớn nhất". Chỉ gắn cho cột cho phép NULL — trên purchased_at,
    # DESC NULLS LAST khiến Postgres bỏ chỉ mục và sắp cả bảng cho trang mặc định.
    if column.nullable:
        ordering = ordering.nulls_last()
    return (
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
            _RISK_LEVEL.label("risk_level"),
        )
        .select_from(_ORDERS_WITH_LATEST_ASSESSMENT)
        .where(*_where(filters))
        # order_id phá hoà để lật trang không trả trùng hay bỏ sót đơn.
        .order_by(ordering, orders.c.order_id)
    )


def _to_item(row: sa.Row) -> OrderListItem:
    return OrderListItem(
        order_id=row.order_id,
        order_status=row.order_status,
        delivery_outcome=_delivery_outcome(row.is_delivered, row.is_late),
        purchased_at=row.purchased_at,
        estimated_delivery_date=row.estimated_delivery_date,
        delivered_at=row.delivered_to_customer_at,
        customer_state=row.customer_state,
        order_value=row.order_value,
        risk_level=row.risk_level,
    )


async def list_orders(
    session: AsyncSession,
    filters: OrderFilters,
    *,
    sort: OrderSort,
    direction: SortDirection,
    page: int,
) -> OrderList:
    """Một trang danh sách đơn khớp mọi điều kiện trong `filters` cùng lúc."""
    # Cùng FROM với _list_statement: risk_level/handling_status lọc trên dòng đã LEFT JOIN
    # LATERAL, nên câu đếm phải qua đúng JOIN đó thì total mới khớp items.
    total = await session.scalar(
        sa.select(sa.func.count())
        .select_from(_ORDERS_WITH_LATEST_ASSESSMENT)
        .where(*_where(filters))
    )
    rows = (
        await session.execute(
            _list_statement(filters, sort, direction)
            .limit(PAGE_SIZE)
            .offset((page - 1) * PAGE_SIZE)
        )
    ).all()

    return OrderList(
        items=[_to_item(row) for row in rows],
        total=total or 0,
        page=page,
        page_size=PAGE_SIZE,
    )


async def export_orders_csv(
    session: AsyncSession,
    filters: OrderFilters,
    *,
    sort: OrderSort,
    direction: SortDirection,
) -> AsyncIterator[str]:
    """Mọi đơn khớp `filters`, theo đúng thứ tự của list_orders, dưới dạng CSV từng lô.

    Cột là tên trường của OrderListItem, nên file và một dòng /orders cùng một hợp đồng.
    Đọc bằng con trỏ phía máy chủ theo lô, không nạp cả 99.441 dòng vào bộ nhớ một lần.
    """
    fields = list(OrderListItem.model_fields)
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    def drain() -> str:
        chunk = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate()
        return chunk

    # BOM để Excel nhận ra UTF-8; thiếu nó Excel đọc theo bảng mã cục bộ và vỡ dấu.
    writer.writerow(fields)
    yield "\ufeff" + drain()

    result = await session.stream(
        _list_statement(filters, sort, direction).execution_options(yield_per=EXPORT_BATCH)
    )
    async for partition in result.partitions():
        for row in partition:
            # mode="json" cho ngày giờ dạng ISO giống hệt /orders; None thành ô trống.
            item = _to_item(row).model_dump(mode="json")
            writer.writerow([item[field] for field in fields])
        yield drain()


def _delivery_outcome(is_delivered: bool, is_late: bool | None) -> DeliveryOutcome:
    if not is_delivered:
        return "no_outcome"
    return "late" if is_late else "on_time"


class OrderTimeline(BaseModel):
    purchased_at: datetime
    payment_approved_at: datetime | None
    handed_to_carrier_at: datetime | None
    delivered_at: datetime | None
    estimated_delivery_date: date
    # Ba chặng tính bằng ngày, đọc từ cột sinh chứ không tính lại. None khi thiếu một
    # trong hai mốc của chặng. Có thể âm: dữ liệu gốc có đơn bàn giao vận chuyển trước lúc
    # duyệt thanh toán, và trang chi tiết hiện nguyên như vậy.
    payment_approval_days: float | None
    seller_handling_days: float | None
    carrier_transit_days: float | None


class OrderItem(BaseModel):
    order_item_id: int
    product_id: str
    # Tên tiếng Anh từ bảng dịch; danh mục chưa có bản dịch giữ tên gốc tiếng Bồ, sản
    # phẩm không có danh mục là None.
    category: str | None
    price: float
    freight_value: float
    seller_id: str


class OrderSeller(BaseModel):
    seller_id: str
    # Seller State: bang người bán gửi hàng đi, khác bang khách nhận ở ShippingAddress.
    seller_city: str
    seller_state: str


class ShippingAddress(BaseModel):
    # Thành phố và mã bưu chính là None nếu đã chạy migration 0007 mà chưa dựng lại bảng
    # dẫn xuất. Trang chi tiết vẫn phải mở được, chỉ ghi là chưa có.
    customer_city: str | None
    customer_state: str
    customer_zip_code_prefix: str | None


class OrderPayment(BaseModel):
    payment_sequential: int
    payment_type: str
    payment_installments: int
    payment_value: float


class OrderReview(BaseModel):
    review_score: int
    comment_title: str | None
    comment_message: str | None
    created_at: datetime


class OrderDetail(BaseModel):
    order_id: str
    order_status: str
    delivery_outcome: DeliveryOutcome
    order_value: float | None
    timeline: OrderTimeline
    address: ShippingAddress
    # Danh sách rỗng nghĩa là đơn không có phần đó — không phải lỗi.
    items: list[OrderItem]
    sellers: list[OrderSeller]
    payments: list[OrderPayment]
    reviews: list[OrderReview]
    # Order Milestone kế tiếp cần ghi nhận, và liệu đơn có hủy được — None/False cho mọi
    # đơn Olist lịch sử (0 dòng risk_assessments, xem app/models/risk.py).
    next_milestone: Milestone | None
    cancelable: bool


def _days(column: sa.ColumnElement) -> sa.ColumnElement:
    # Cùng cách quy đổi INTERVAL sang số ngày với _stage_percentiles của bảng điều khiển.
    return sa.extract("epoch", column) / 86400.0


async def get_order_detail(session: AsyncSession, order_id: str) -> OrderDetail | None:
    """Mọi thứ về một đơn cho trang chi tiết; None nếu không có đơn nào mang mã đó.

    Mỗi phần một truy vấn nhỏ theo order_id thay vì một câu JOIN lớn: sản phẩm, thanh toán
    và đánh giá là các danh sách độc lập, JOIN chung sẽ nhân chéo số dòng của nhau.
    """
    has_assessment = sa.exists(
        sa.select(1).where(risk_assessments.c.order_id == orders.c.order_id)
    ).label("has_assessment")
    order = (
        await session.execute(
            sa.select(
                orders.c.order_id,
                orders.c.order_status,
                orders.c.order_value,
                orders.c.is_late,
                DELIVERED.label("is_delivered"),
                orders.c.purchased_at,
                orders.c.payment_approved_at,
                orders.c.handed_to_carrier_at,
                orders.c.delivered_to_customer_at,
                orders.c.estimated_delivery_date,
                _days(orders.c.payment_approval).label("payment_approval_days"),
                _days(orders.c.seller_handling).label("seller_handling_days"),
                _days(orders.c.carrier_transit).label("carrier_transit_days"),
                orders.c.customer_city,
                orders.c.customer_state,
                orders.c.customer_zip_code_prefix,
                has_assessment,
            ).where(orders.c.order_id == order_id)
        )
    ).one_or_none()
    if order is None:
        return None

    items = (
        await session.execute(
            sa.select(
                order_items.c.order_item_id,
                order_items.c.product_id,
                sa.func.coalesce(
                    product_categories.c.product_category_name_english,
                    order_items.c.product_category_name,
                ).label("category"),
                order_items.c.price,
                order_items.c.freight_value,
                order_items.c.seller_id,
            )
            .select_from(order_items)
            .outerjoin(
                product_categories,
                product_categories.c.product_category_name
                == order_items.c.product_category_name,
            )
            .where(order_items.c.order_id == order_id)
            .order_by(order_items.c.order_item_id)
        )
    ).all()
    order_sellers_rows = (
        await session.execute(
            sa.select(sellers.c.seller_id, sellers.c.seller_city, sellers.c.seller_state)
            .join(order_sellers, order_sellers.c.seller_id == sellers.c.seller_id)
            .where(order_sellers.c.order_id == order_id)
            .order_by(sellers.c.seller_id)
        )
    ).all()
    payments = (
        await session.execute(
            sa.select(
                order_payments.c.payment_sequential,
                order_payments.c.payment_type,
                order_payments.c.payment_installments,
                order_payments.c.payment_value,
            )
            .where(order_payments.c.order_id == order_id)
            .order_by(order_payments.c.payment_sequential)
        )
    ).all()
    reviews = (
        await session.execute(
            sa.select(
                order_reviews.c.review_score,
                order_reviews.c.comment_title,
                order_reviews.c.comment_message,
                order_reviews.c.review_created_at,
            )
            .where(order_reviews.c.order_id == order_id)
            # Thứ tự đã đóng cứng lúc dựng bảng: sắp theo riêng thời điểm tạo là bất định
            # với các đơn có nhiều đánh giá cùng ngày.
            .order_by(order_reviews.c.review_sequential)
        )
    ).all()

    return OrderDetail(
        order_id=order.order_id,
        order_status=order.order_status,
        delivery_outcome=_delivery_outcome(order.is_delivered, order.is_late),
        order_value=order.order_value,
        timeline=OrderTimeline(
            purchased_at=order.purchased_at,
            payment_approved_at=order.payment_approved_at,
            handed_to_carrier_at=order.handed_to_carrier_at,
            delivered_at=order.delivered_to_customer_at,
            estimated_delivery_date=order.estimated_delivery_date,
            payment_approval_days=order.payment_approval_days,
            seller_handling_days=order.seller_handling_days,
            carrier_transit_days=order.carrier_transit_days,
        ),
        address=ShippingAddress(
            customer_city=order.customer_city,
            customer_state=order.customer_state,
            customer_zip_code_prefix=order.customer_zip_code_prefix,
        ),
        items=[
            OrderItem(
                order_item_id=row.order_item_id,
                product_id=row.product_id,
                category=row.category,
                price=row.price,
                freight_value=row.freight_value,
                seller_id=row.seller_id,
            )
            for row in items
        ],
        sellers=[
            OrderSeller(
                seller_id=row.seller_id,
                seller_city=row.seller_city,
                seller_state=row.seller_state,
            )
            for row in order_sellers_rows
        ],
        payments=[
            OrderPayment(
                payment_sequential=row.payment_sequential,
                payment_type=row.payment_type,
                payment_installments=row.payment_installments,
                payment_value=row.payment_value,
            )
            for row in payments
        ],
        reviews=[
            OrderReview(
                review_score=row.review_score,
                comment_title=row.comment_title,
                comment_message=row.comment_message,
                created_at=row.review_created_at,
            )
            for row in reviews
        ],
        next_milestone=next_milestone(
            has_assessment=order.has_assessment,
            order_status=order.order_status,
            payment_approved_at=order.payment_approved_at,
            handed_to_carrier_at=order.handed_to_carrier_at,
            delivered_to_customer_at=order.delivered_to_customer_at,
        ),
        cancelable=is_cancelable(
            has_assessment=order.has_assessment, order_status=order.order_status
        ),
    )


async def list_customer_states(session: AsyncSession) -> list[str]:
    """Mọi bang có đơn, không áp bộ lọc nào.

    Khác list_customer_states của bảng điều khiển, vốn chỉ đếm đơn đã giao: danh sách đơn
    gồm cả đơn chưa giao, nên một bang chỉ có đơn đang trên đường vẫn phải chọn được.
    """
    rows = await session.scalars(
        sa.select(orders.c.customer_state).distinct().order_by(orders.c.customer_state)
    )
    return list(rows.all())
