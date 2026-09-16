import sqlalchemy as sa

from app.core.db import Base

orders = sa.Table(
    "orders",
    Base.metadata,
    sa.Column("order_id", sa.Text, primary_key=True),
    sa.Column("order_status", sa.Text, nullable=False),
    sa.Column("customer_state", sa.Text, nullable=False, index=True),
    # Địa chỉ giao cho trang chi tiết đơn. Mã bưu chính là chuỗi 5 chữ số chứ không phải
    # số: cột thô là số nguyên nên đã mất số 0 đầu — xem build_derived_data.py.
    sa.Column("customer_city", sa.Text),
    sa.Column("customer_zip_code_prefix", sa.Text),
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

# Dòng sản phẩm của một đơn. Khoá ngoại tới orders an toàn vì bảng này được truncate và dựng
# lại cùng lượt với orders — khác order_notes, vốn phải sống sót qua mỗi lần dựng lại.
#
# Lưu tên danh mục GỐC chứ không phải nhãn tiếng Anh đã tra sẵn: nhãn nằm ở
# product_categories, để riêng thì sửa bản dịch không phải dựng lại 112.650 dòng.
order_items = sa.Table(
    "order_items",
    Base.metadata,
    sa.Column("order_id", sa.Text, sa.ForeignKey("orders.order_id"), primary_key=True),
    sa.Column("order_item_id", sa.Integer, primary_key=True),
    sa.Column("product_id", sa.Text, nullable=False),
    sa.Column("product_category_name", sa.Text),
    # Mô hình dự đoán cần cân nặng; trang chi tiết đơn không hiện nó.
    sa.Column("product_weight_g", sa.Integer),
    sa.Column("price", sa.Numeric(12, 2), nullable=False),
    sa.Column("freight_value", sa.Numeric(12, 2), nullable=False),
    sa.Column("seller_id", sa.Text, nullable=False),
)

order_payments = sa.Table(
    "order_payments",
    Base.metadata,
    sa.Column("order_id", sa.Text, sa.ForeignKey("orders.order_id"), primary_key=True),
    sa.Column("payment_sequential", sa.Integer, primary_key=True),
    sa.Column("payment_type", sa.Text, nullable=False),
    sa.Column("payment_installments", sa.Integer, nullable=False),
    sa.Column("payment_value", sa.Numeric(12, 2), nullable=False),
)

# review_sequential: 547 đơn Olist có nhiều hơn một đánh giá, nên order_id một mình không làm
# khoá chính được. Nó cũng là mốc sắp xếp cố định — 157 cặp (order_id, ngày tạo) trùng nhau
# nên sắp theo riêng ngày tạo là bất định.
#
# Tên cột không đồng nhất tiền tố là có chủ đích: comment_title và comment_message lấy đúng
# tên trường của phản hồi API, còn review_created_at thì cố ý KHÔNG đặt là created_at —
# order_notes.created_at là mốc thật có múi giờ, còn đây là dấu thời gian không múi giờ của
# dữ liệu Olist, và hai thứ đó không được lẫn vào nhau.
order_reviews = sa.Table(
    "order_reviews",
    Base.metadata,
    sa.Column("order_id", sa.Text, sa.ForeignKey("orders.order_id"), primary_key=True),
    sa.Column("review_sequential", sa.Integer, primary_key=True),
    sa.Column("review_score", sa.SmallInteger, nullable=False),
    sa.Column("comment_title", sa.Text),
    sa.Column("comment_message", sa.Text),
    sa.Column("review_created_at", sa.DateTime, nullable=False),
)

# Nhãn tiếng Anh của danh mục sản phẩm. Hai danh mục chưa có bản dịch (pc_gamer,
# portateis_cozinha_e_preparadores_de_alimentos) cố ý không có ở đây: dòng sản phẩm thuộc
# chúng vẫn hiện tên gốc nhờ coalesce ở đường đọc.
product_categories = sa.Table(
    "product_categories",
    Base.metadata,
    sa.Column("product_category_name", sa.Text, primary_key=True),
    sa.Column("product_category_name_english", sa.Text, nullable=False),
)
