"""Bốn thao tác đưa một đơn Ship Guard đi tiếp trong vòng đời — #33.

Không phải module lá: import từ `risk_assessments.py` (dùng lại `insert_assessment`,
`_load_sellers`, `SellerZipMissingError`, `RiskAssessmentOut`) và từ `order_milestones.py`
(suy luận thuần, không đụng DB). `services/orders.py` KHÔNG import từ đây — nó import thẳng
từ `order_milestones.py` — để không khép vòng import (xem kế hoạch #33, mục 1.1).
"""

from datetime import datetime, timezone
from typing import Literal

import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.derived import order_items, order_payments, orders
from app.models.risk import risk_assessments
from app.risk.predictor import OrderInput, OrderLine, RiskPredictor
from app.services.order_milestones import (
    MILESTONE_SEQUENCE,
    MILESTONE_STATUS,
    Milestone,
    is_cancelable,
    next_milestone,
)
from app.services.risk_assessments import (
    RiskAssessmentOut,
    SellerZipMissingError,
    _load_sellers,
    insert_assessment,
)

# Cột mốc trên `orders` ứng với mỗi Order Milestone, và tên thuộc tính của mốc LIỀN
# TRƯỚC nó trên cùng dòng — dùng để kiểm "recorded_at không sớm hơn mốc trước".
_MILESTONE_COLUMN: dict[Milestone, str] = {
    "payment_approved": "payment_approved_at",
    "handed_to_carrier": "handed_to_carrier_at",
    "delivered_to_customer": "delivered_to_customer_at",
}
_PREVIOUS_TIMESTAMP_ATTR: dict[Milestone, str] = {
    "payment_approved": "purchased_at",
    "handed_to_carrier": "payment_approved_at",
    "delivered_to_customer": "handed_to_carrier_at",
}


class OrderNotFoundError(Exception):
    """404: order_id không tồn tại."""


class InvalidMilestoneTimestampError(Exception):
    """422 — cùng khuôn [{type, loc, msg}] của InvalidOrderError, loc=("recorded_at",).

    Một lỗi hợp lệ hóa đúng nghĩa trên trường duy nhất endpoint nhận, khác năm lỗi 409
    dưới đây vốn là xung đột trạng thái trên một tài nguyên chắc chắn tồn tại.
    """

    def __init__(self, msg: str) -> None:
        self.msg = msg
        super().__init__(msg)


class LifecycleConflictError(Exception):
    """409: xung đột trạng thái. `code` cho phép giao diện rẽ nhánh, không so chuỗi."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class NotShipGuardOrderError(LifecycleConflictError):
    def __init__(self, order_id: str) -> None:
        super().__init__(
            "not_ship_guard_order",
            f"Order {order_id} has no Risk Assessment yet and is not managed by Ship Guard",
        )


class OrderAlreadyDeliveredError(LifecycleConflictError):
    def __init__(self, order_id: str) -> None:
        super().__init__(
            "already_delivered", f"Order {order_id} has already been delivered"
        )


class OrderAlreadyCanceledError(LifecycleConflictError):
    def __init__(self, order_id: str) -> None:
        super().__init__(
            "already_canceled", f"Order {order_id} has already been canceled"
        )


class OutOfOrderMilestoneError(LifecycleConflictError):
    def __init__(self, expected: Milestone | None, got: Milestone) -> None:
        super().__init__(
            "out_of_order_milestone",
            f"The next milestone for this order is {expected!r}, not {got!r}",
        )


class NotLatestMilestoneError(LifecycleConflictError):
    def __init__(self, latest: Milestone | None, requested: Milestone) -> None:
        super().__init__(
            "not_latest_milestone",
            f"The latest recorded milestone is {latest!r}, not {requested!r}",
        )


class OrderChangedConcurrentlyError(LifecycleConflictError):
    """Dự phòng: chỉ nổ ra nếu UPDATE có điều kiện bị 0 dòng khớp mà đọc lại đơn vẫn
    không giải thích được lý do cụ thể (canceled/delivered/mốc đã đổi) — về lý thuyết
    không nên xảy ra vì điều kiện WHERE đã phủ đúng các trường hợp đó, nhưng giữ lại để
    hàm luôn có một lỗi rõ ràng thay vì rơi qua đáy."""

    def __init__(self, order_id: str) -> None:
        super().__init__(
            "order_changed_concurrently",
            f"Order {order_id} was changed by another request; reload and retry",
        )


class RecordMilestone(BaseModel):
    milestone: Milestone
    recorded_at: datetime


class EditMilestoneTimestamp(BaseModel):
    recorded_at: datetime


class MilestoneRecorded(BaseModel):
    order_id: str
    order_status: str
    next_milestone: Milestone | None
    cancelable: bool
    # None đúng khi milestone == "delivered_to_customer": mốc đó chạy Reconciliation,
    # không sinh Risk Assessment mới.
    risk_assessment: RiskAssessmentOut | None


class CanceledOrder(BaseModel):
    order_id: str
    order_status: Literal["canceled"]


def _to_naive_utc(value: datetime) -> datetime:
    # Cùng quy ước với create_new_order: mọi mốc đơn lưu naive theo giờ UTC.
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _validate_recorded_at(recorded_at: datetime, *, not_before: datetime | None) -> None:
    if recorded_at.tzinfo is None:
        raise InvalidMilestoneTimestampError("recorded_at must include a UTC offset")
    if recorded_at > datetime.now(timezone.utc):
        raise InvalidMilestoneTimestampError("recorded_at cannot be in the future")
    if not_before is not None and _to_naive_utc(recorded_at) < not_before:
        raise InvalidMilestoneTimestampError(
            "recorded_at cannot be earlier than the previous milestone"
        )


async def _has_assessment(session: AsyncSession, order_id: str) -> bool:
    found = await session.scalar(
        sa.select(1).where(risk_assessments.c.order_id == order_id).limit(1)
    )
    return found is not None


def _latest_milestone(order: sa.Row) -> Milestone | None:
    for milestone in reversed(MILESTONE_SEQUENCE):
        if getattr(order, _MILESTONE_COLUMN[milestone]) is not None:
            return milestone
    return None


def _later_milestones(milestone: Milestone) -> tuple[Milestone, ...]:
    index = MILESTONE_SEQUENCE.index(milestone)
    return MILESTONE_SEQUENCE[index + 1 :]


async def _load_order_row(session: AsyncSession, order_id: str) -> sa.Row | None:
    return (
        await session.execute(
            sa.select(
                orders.c.order_status,
                orders.c.purchased_at,
                orders.c.payment_approved_at,
                orders.c.handed_to_carrier_at,
                orders.c.delivered_to_customer_at,
            ).where(orders.c.order_id == order_id)
        )
    ).one_or_none()


async def _check_gates(session: AsyncSession, order_id: str, order: sa.Row | None) -> bool:
    """Bốn cổng chung của cả bốn thao tác: tồn tại, có Risk Assessment, chưa hủy, chưa giao.

    Trả về `has_assessment` — người gọi cần giá trị này để dựng `MilestoneRecorded`/kiểm
    `cancelable` mà không phải truy vấn lại.
    """
    if order is None:
        raise OrderNotFoundError(order_id)
    has_assessment = await _has_assessment(session, order_id)
    if not has_assessment:
        raise NotShipGuardOrderError(order_id)
    if order.order_status == "canceled":
        raise OrderAlreadyCanceledError(order_id)
    if order.order_status == "delivered":
        raise OrderAlreadyDeliveredError(order_id)
    return has_assessment


async def load_order_input(
    session: AsyncSession,
    order_id: str,
    *,
    payment_approved_at: datetime | None,
    handed_to_carrier_at: datetime | None,
) -> OrderInput:
    """Dựng lại `OrderInput` của một đơn đã tồn tại, cho bộ dự đoán chấm ở mốc mới.

    `payment_approved_at`/`handed_to_carrier_at` là giá trị MỚI NHẤT tính đến thời điểm
    gọi — người gọi (record_milestone/edit_milestone) luôn truyền đủ cả mốc vừa đổi lẫn
    mốc chốt trước đó, không chỉ mốc vừa đổi, nếu không `_checkpoint()`/`_settled_days()`
    (predictor.py:236-260) suy sai chặng.
    """
    order = (
        await session.execute(
            sa.select(
                orders.c.purchased_at,
                orders.c.customer_state,
                orders.c.customer_zip_code_prefix,
                orders.c.estimated_delivery_date,
            ).where(orders.c.order_id == order_id)
        )
    ).one()
    items = (
        await session.execute(
            sa.select(
                order_items.c.seller_id,
                order_items.c.product_category_name,
                order_items.c.product_weight_g,
                order_items.c.price,
                order_items.c.freight_value,
            ).where(order_items.c.order_id == order_id)
        )
    ).all()
    payments = (
        await session.execute(
            sa.select(
                order_payments.c.payment_type, order_payments.c.payment_installments
            ).where(order_payments.c.order_id == order_id)
        )
    ).all()

    seller_by_id = await _load_sellers(session, {item.seller_id for item in items})
    missing_zip = next(
        (
            seller_id
            for seller_id, row in seller_by_id.items()
            if row.seller_zip_code_prefix is None
        ),
        None,
    )
    if missing_zip is not None:
        raise SellerZipMissingError(missing_zip)

    lines = tuple(
        OrderLine(
            seller_id=item.seller_id,
            seller_state=seller_by_id[item.seller_id].seller_state,
            seller_zip=seller_by_id[item.seller_id].seller_zip_code_prefix,
            product_category_name=item.product_category_name,
            product_weight_g=item.product_weight_g,
            price=item.price,
            freight_value=item.freight_value,
        )
        for item in items
    )
    # Cùng cách gộp payment_types/payment_installments với _build_order_input.
    payment_types = tuple(sorted({payment.payment_type for payment in payments}))
    max_installments = max(payment.payment_installments for payment in payments)

    return OrderInput(
        order_id=order_id,
        purchased_at=order.purchased_at,
        estimated_delivery_date=order.estimated_delivery_date,
        customer_state=order.customer_state,
        customer_zip=order.customer_zip_code_prefix,
        lines=lines,
        payment_types=payment_types,
        payment_installments=max_installments,
        payment_approved_at=payment_approved_at,
        handed_to_carrier_at=handed_to_carrier_at,
    )


async def record_milestone(
    session: AsyncSession,
    predictor: RiskPredictor,
    order_id: str,
    payload: RecordMilestone,
    current_user_id: int,
) -> MilestoneRecorded:
    order = await _load_order_row(session, order_id)
    has_assessment = await _check_gates(session, order_id, order)

    expected = next_milestone(
        has_assessment=has_assessment,
        order_status=order.order_status,
        payment_approved_at=order.payment_approved_at,
        handed_to_carrier_at=order.handed_to_carrier_at,
        delivered_to_customer_at=order.delivered_to_customer_at,
    )
    if payload.milestone != expected:
        raise OutOfOrderMilestoneError(expected, payload.milestone)

    previous_at = getattr(order, _PREVIOUS_TIMESTAMP_ATTR[payload.milestone])
    _validate_recorded_at(payload.recorded_at, not_before=previous_at)
    recorded_at = _to_naive_utc(payload.recorded_at)
    column_name = _MILESTONE_COLUMN[payload.milestone]
    new_status = MILESTONE_STATUS[payload.milestone]

    # WHERE cột mốc còn NULL VÀ order_status chưa đổi kể từ lúc đọc: chặn cả hai đường
    # đua — (1) hai request ghi cùng một mốc, (2) một request đang ghi mốc trong lúc một
    # request khác vừa hủy đơn. Không khớp WHERE thì đơn đã đổi trạng thái từ lúc đọc,
    # đọc lại để trả đúng lỗi (đã hủy/đã giao/mốc đã bị lấp) thay vì luôn báo
    # OutOfOrderMilestoneError sai ngữ cảnh.
    result = await session.execute(
        sa.update(orders)
        .where(
            orders.c.order_id == order_id,
            orders.c[column_name].is_(None),
            orders.c.order_status == order.order_status,
        )
        .values(**{column_name: recorded_at, "order_status": new_status})
        .returning(orders.c.is_late)
    )
    updated = result.one_or_none()
    if updated is None:
        fresh_order = await _load_order_row(session, order_id)
        await _check_gates(session, order_id, fresh_order)
        fresh_expected = next_milestone(
            has_assessment=True,
            order_status=fresh_order.order_status,
            payment_approved_at=fresh_order.payment_approved_at,
            handed_to_carrier_at=fresh_order.handed_to_carrier_at,
            delivered_to_customer_at=fresh_order.delivered_to_customer_at,
        )
        raise OutOfOrderMilestoneError(fresh_expected, payload.milestone)
    is_late = updated.is_late

    timestamps = {
        "payment_approved_at": order.payment_approved_at,
        "handed_to_carrier_at": order.handed_to_carrier_at,
        "delivered_to_customer_at": order.delivered_to_customer_at,
        column_name: recorded_at,
    }

    assessment: RiskAssessmentOut | None = None
    if payload.milestone == "delivered_to_customer":
        # Reconciliation: đối chiếu MỌI dòng lịch sử của đơn, không chỉ dòng mới nhất.
        await session.execute(
            sa.update(risk_assessments)
            .where(risk_assessments.c.order_id == order_id)
            .values(was_correct=(risk_assessments.c.is_high_risk == is_late))
        )
    else:
        order_input = await load_order_input(
            session,
            order_id,
            payment_approved_at=timestamps["payment_approved_at"],
            handed_to_carrier_at=timestamps["handed_to_carrier_at"],
        )
        assessment = await insert_assessment(
            session, predictor, order_id, order_input, current_user_id
        )

    await session.commit()

    return MilestoneRecorded(
        order_id=order_id,
        order_status=new_status,
        next_milestone=next_milestone(
            has_assessment=True,
            order_status=new_status,
            payment_approved_at=timestamps["payment_approved_at"],
            handed_to_carrier_at=timestamps["handed_to_carrier_at"],
            delivered_to_customer_at=timestamps["delivered_to_customer_at"],
        ),
        cancelable=is_cancelable(has_assessment=True, order_status=new_status),
        risk_assessment=assessment,
    )


async def edit_milestone(
    session: AsyncSession,
    predictor: RiskPredictor,
    order_id: str,
    milestone: Milestone,
    payload: EditMilestoneTimestamp,
    current_user_id: int,
) -> MilestoneRecorded:
    order = await _load_order_row(session, order_id)
    await _check_gates(session, order_id, order)

    latest = _latest_milestone(order)
    if milestone != latest:
        raise NotLatestMilestoneError(latest, milestone)

    previous_at = getattr(order, _PREVIOUS_TIMESTAMP_ATTR[milestone])
    _validate_recorded_at(payload.recorded_at, not_before=previous_at)
    recorded_at = _to_naive_utc(payload.recorded_at)
    column_name = _MILESTONE_COLUMN[milestone]
    old_value = getattr(order, column_name)

    # WHERE giá trị cột mốc chưa đổi (chặn sửa-sửa đua nhau), mọi mốc SAU nó vẫn còn
    # NULL (chặn edit đè lên một đơn vừa được record_milestone đẩy đi tiếp — mốc đang
    # sửa không còn là "mới nhất" nữa dù cột của chính nó chưa đổi), và order_status
    # chưa đổi (chặn edit đè lên một đơn vừa bị hủy). Không khớp thì đọc lại để báo
    # đúng lỗi thay vì âm thầm ghi đè.
    result = await session.execute(
        sa.update(orders)
        .where(
            orders.c.order_id == order_id,
            orders.c[column_name] == old_value,
            orders.c.order_status == order.order_status,
            *(orders.c[_MILESTONE_COLUMN[m]].is_(None) for m in _later_milestones(milestone)),
        )
        .values(**{column_name: recorded_at})
        .returning(orders.c.order_id)
    )
    if result.one_or_none() is None:
        fresh_order = await _load_order_row(session, order_id)
        await _check_gates(session, order_id, fresh_order)
        raise NotLatestMilestoneError(_latest_milestone(fresh_order), milestone)

    timestamps = {
        "payment_approved_at": order.payment_approved_at,
        "handed_to_carrier_at": order.handed_to_carrier_at,
        "delivered_to_customer_at": order.delivered_to_customer_at,
        column_name: recorded_at,
    }

    # "Mốc đã giao không sửa được" đúng về cấu trúc: milestone == "delivered_to_customer"
    # chỉ có thể là mốc mới nhất khi order_status == "delivered", và nhánh đó đã bị chặn
    # ở _check_gates phía trên — nên nhánh else dưới đây chỉ còn payment_approved/
    # handed_to_carrier, giữ nguyên order_status hiện tại (chưa đổi ở PATCH).
    assessment: RiskAssessmentOut | None = None
    if milestone != "delivered_to_customer":
        order_input = await load_order_input(
            session,
            order_id,
            payment_approved_at=timestamps["payment_approved_at"],
            handed_to_carrier_at=timestamps["handed_to_carrier_at"],
        )
        assessment = await insert_assessment(
            session, predictor, order_id, order_input, current_user_id
        )

    await session.commit()

    return MilestoneRecorded(
        order_id=order_id,
        order_status=order.order_status,
        next_milestone=next_milestone(
            has_assessment=True,
            order_status=order.order_status,
            payment_approved_at=timestamps["payment_approved_at"],
            handed_to_carrier_at=timestamps["handed_to_carrier_at"],
            delivered_to_customer_at=timestamps["delivered_to_customer_at"],
        ),
        cancelable=is_cancelable(has_assessment=True, order_status=order.order_status),
        risk_assessment=assessment,
    )


async def cancel_order(session: AsyncSession, order_id: str) -> CanceledOrder:
    order = await _load_order_row(session, order_id)
    await _check_gates(session, order_id, order)

    # WHERE order_status chưa ở trạng thái chốt (delivered/canceled) — không so bằng
    # đúng giá trị đã đọc, vì một mốc trung gian (vd created → approved) đổi đồng thời
    # không làm hủy đơn sai, chỉ có tới trạng thái chốt mới thật sự xung đột với hủy.
    # Không khớp thì một request khác vừa giao/hủy đơn trước — đọc lại để báo đúng lỗi.
    result = await session.execute(
        sa.update(orders)
        .where(
            orders.c.order_id == order_id,
            orders.c.order_status.not_in(("canceled", "delivered")),
        )
        .values(order_status="canceled")
        .returning(orders.c.order_id)
    )
    if result.one_or_none() is None:
        fresh_order = await _load_order_row(session, order_id)
        await _check_gates(session, order_id, fresh_order)
        raise OrderChangedConcurrentlyError(order_id)
    await session.commit()
    return CanceledOrder(order_id=order_id, order_status="canceled")
