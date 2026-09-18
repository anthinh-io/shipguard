"""Suy luận thuần về Order Milestone — không import gì từ app/services/, không đụng DB.

Module lá: cả `services/orders.py` (cho `OrderDetail`) và `services/order_lifecycle.py`
(cho việc ghi nhận/sửa mốc) đều import từ đây, để tránh vòng lặp import giữa hai module
đó — xem kế hoạch #33, mục 1.1.
"""

from typing import Literal

Milestone = Literal["payment_approved", "handed_to_carrier", "delivered_to_customer"]

MILESTONE_SEQUENCE: tuple[Milestone, ...] = (
    "payment_approved",
    "handed_to_carrier",
    "delivered_to_customer",
)

MILESTONE_STATUS: dict[Milestone, str] = {
    "payment_approved": "approved",
    "handed_to_carrier": "shipped",
    "delivered_to_customer": "delivered",
}


def next_milestone(
    *,
    has_assessment: bool,
    order_status: str,
    payment_approved_at,
    handed_to_carrier_at,
    delivered_to_customer_at,
) -> Milestone | None:
    if not has_assessment or order_status in ("delivered", "canceled"):
        return None
    if payment_approved_at is None:
        return "payment_approved"
    if handed_to_carrier_at is None:
        return "handed_to_carrier"
    if delivered_to_customer_at is None:
        return "delivered_to_customer"
    return None


def is_cancelable(*, has_assessment: bool, order_status: str) -> bool:
    return has_assessment and order_status not in ("delivered", "canceled")


# Diễn giải đúng ngay cả khi MILESTONE_SEQUENCE đổi thứ tự/thêm mốc sau này — khác suy theo
# vị trí ("mốc cuối cùng của dãy"), vốn là một sự tình cờ về vị trí chứ không phải ý nghĩa.
def is_delivery_milestone(milestone: Milestone) -> bool:
    return MILESTONE_STATUS[milestone] == "delivered"
