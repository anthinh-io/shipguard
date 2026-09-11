import sqlalchemy as sa

from app.core.db import Base

orders = sa.Table(
    "orders",
    Base.metadata,
    sa.Column("order_id", sa.Text, primary_key=True),
    sa.Column("order_status", sa.Text, nullable=False),
    sa.Column("customer_state", sa.Text, nullable=False, index=True),
    sa.Column("purchased_at", sa.DateTime, nullable=False),
    sa.Column("payment_approved_at", sa.DateTime),
    sa.Column("handed_to_carrier_at", sa.DateTime),
    sa.Column("delivered_to_customer_at", sa.DateTime, index=True),
    sa.Column("estimated_delivery_date", sa.Date, nullable=False),
    # Điểm thấp nhất trong các đánh giá của đơn — xem build_derived_data.py.
    sa.Column("worst_review_score", sa.SmallInteger),
    sa.Column(
        "payment_approval",
        sa.Interval,
        sa.Computed("payment_approved_at - purchased_at", persisted=True),
    ),
    sa.Column(
        "seller_handling",
        sa.Interval,
        sa.Computed("handed_to_carrier_at - payment_approved_at", persisted=True),
    ),
    sa.Column(
        "carrier_transit",
        sa.Interval,
        sa.Computed("delivered_to_customer_at - handed_to_carrier_at", persisted=True),
    ),
    # Phép so ở mức ngày lịch được đóng cứng vào lược đồ. Kiểu DATE của
    # estimated_delivery_date một mình không đủ: so thẳng dấu thời gian với nó vẫn
    # nâng DATE lên nửa đêm và cho ra 7.826 đơn trễ thay vì 6.534. Truy vấn KPI đọc
    # cờ này, không tự tính lại.
    #
    # Cả bốn biểu thức phải IMMUTABLE. Chúng đúng như vậy vì các cột là
    # TIMESTAMP WITHOUT TIME ZONE — thêm timezone=True sẽ làm migration hỏng với
    # "generation expression is not immutable".
    sa.Column(
        "is_late",
        sa.Boolean,
        sa.Computed(
            "delivered_to_customer_at::date > estimated_delivery_date", persisted=True
        ),
    ),
)

order_sellers = sa.Table(
    "order_sellers",
    Base.metadata,
    sa.Column("order_id", sa.Text, sa.ForeignKey("orders.order_id"), primary_key=True),
    sa.Column("seller_id", sa.Text, primary_key=True, index=True),
)
