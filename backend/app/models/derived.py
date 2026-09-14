import sqlalchemy as sa

from app.core.db import Base

orders = sa.Table(
    "orders",
    Base.metadata,
    sa.Column("order_id", sa.Text, primary_key=True),
    sa.Column("order_status", sa.Text, nullable=False),
    sa.Column("customer_state", sa.Text, nullable=False, index=True),
    sa.Column("purchased_at", sa.DateTime, nullable=False, index=True),
    sa.Column("payment_approved_at", sa.DateTime),
    sa.Column("handed_to_carrier_at", sa.DateTime),
    sa.Column("delivered_to_customer_at", sa.DateTime, index=True),
    sa.Column("estimated_delivery_date", sa.Date, nullable=False),
    # Điểm thấp nhất trong các đánh giá của đơn — xem build_derived_data.py.
    sa.Column("worst_review_score", sa.SmallInteger),
    # Order Value theo CONTEXT.md: tổng price + freight_value của các sản phẩm, NULL khi
    # đơn không có sản phẩm nào. Không phải số tiền đã thanh toán — 303 đơn lệch tổng
    # thanh toán hơn 1 xu, và như vậy là đúng.
    sa.Column("order_value", sa.Numeric(12, 2)),
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

# Tìm mã đơn khớp tiền tố không phân biệt hoa thường. Khoá chính không dùng được: CSDL
# chạy collation en_US.utf8, mà btree theo collation đó không phục vụ LIKE 'abc%';
# text_pattern_ops thì có. ILIKE không đi qua chỉ mục nào kiểu này, nên truy vấn phải
# viết đúng dạng lower(order_id) LIKE ... để khớp biểu thức.
sa.Index(
    "ix_orders_order_id_prefix",
    sa.func.lower(orders.c.order_id).label("order_id_lower"),
    postgresql_ops={"order_id_lower": "text_pattern_ops"},
)

order_sellers = sa.Table(
    "order_sellers",
    Base.metadata,
    sa.Column("order_id", sa.Text, sa.ForeignKey("orders.order_id"), primary_key=True),
    sa.Column("seller_id", sa.Text, primary_key=True, index=True),
)

# Seller State theo CONTEXT.md: bang người bán GỬI hàng đi, chỉ dùng để nhận diện người
# bán trong ô gợi ý. Mọi chỉ số theo vùng đọc orders.customer_state, tức Region.
#
# Để riêng một bảng vài nghìn dòng thay vì nhồi hai cột vào order_sellers: bảng nối có
# ~100 nghìn dòng và không truy vấn nào của bảng điều khiển cần bang người bán trên đó.
sellers = sa.Table(
    "sellers",
    Base.metadata,
    sa.Column("seller_id", sa.Text, primary_key=True),
    sa.Column("seller_city", sa.Text, nullable=False),
    sa.Column("seller_state", sa.Text, nullable=False),
)
