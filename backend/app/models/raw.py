import sqlalchemy as sa

from app.core.db import Base

raw_customers = sa.Table(
    "raw_customers",
    Base.metadata,
    sa.Column("customer_id", sa.Text),
    sa.Column("customer_unique_id", sa.Text),
    sa.Column("customer_zip_code_prefix", sa.Integer),
    sa.Column("customer_city", sa.Text),
    sa.Column("customer_state", sa.Text),
)

raw_geolocation = sa.Table(
    "raw_geolocation",
    Base.metadata,
    sa.Column("geolocation_zip_code_prefix", sa.Integer),
    sa.Column("geolocation_lat", sa.Double),
    sa.Column("geolocation_lng", sa.Double),
    sa.Column("geolocation_city", sa.Text),
    sa.Column("geolocation_state", sa.Text),
)

raw_order_items = sa.Table(
    "raw_order_items",
    Base.metadata,
    sa.Column("order_id", sa.Text),
    sa.Column("order_item_id", sa.Integer),
    sa.Column("product_id", sa.Text),
    sa.Column("seller_id", sa.Text),
    sa.Column("shipping_limit_date", sa.DateTime),
    sa.Column("price", sa.Numeric(12, 2)),
    sa.Column("freight_value", sa.Numeric(12, 2)),
    # Trang chi tiết đơn tra sản phẩm, thanh toán và đánh giá theo từng order_id.
    sa.Index("ix_raw_order_items_order_id", "order_id"),
)

raw_order_payments = sa.Table(
    "raw_order_payments",
    Base.metadata,
    sa.Column("order_id", sa.Text),
    sa.Column("payment_sequential", sa.Integer),
    sa.Column("payment_type", sa.Text),
    sa.Column("payment_installments", sa.Integer),
    sa.Column("payment_value", sa.Numeric(12, 2)),
    sa.Index("ix_raw_order_payments_order_id", "order_id"),
)

raw_order_reviews = sa.Table(
    "raw_order_reviews",
    Base.metadata,
    sa.Column("review_id", sa.Text),
    sa.Column("order_id", sa.Text),
    sa.Column("review_score", sa.Integer),
    sa.Column("review_comment_title", sa.Text),
    sa.Column("review_comment_message", sa.Text),
    sa.Column("review_creation_date", sa.DateTime),
    sa.Column("review_answer_timestamp", sa.DateTime),
    sa.Index("ix_raw_order_reviews_order_id", "order_id"),
)

raw_orders = sa.Table(
    "raw_orders",
    Base.metadata,
    sa.Column("order_id", sa.Text),
    sa.Column("customer_id", sa.Text),
    sa.Column("order_status", sa.Text),
    sa.Column("order_purchase_timestamp", sa.DateTime),
    sa.Column("order_approved_at", sa.DateTime),
    sa.Column("order_delivered_carrier_date", sa.DateTime),
    sa.Column("order_delivered_customer_date", sa.DateTime),
    sa.Column("order_estimated_delivery_date", sa.DateTime),
)

raw_products = sa.Table(
    "raw_products",
    Base.metadata,
    sa.Column("product_id", sa.Text),
    sa.Column("product_category_name", sa.Text),
    sa.Column("product_name_lenght", sa.Integer),
    sa.Column("product_description_lenght", sa.Integer),
    sa.Column("product_photos_qty", sa.Integer),
    sa.Column("product_weight_g", sa.Integer),
    sa.Column("product_length_cm", sa.Integer),
    sa.Column("product_height_cm", sa.Integer),
    sa.Column("product_width_cm", sa.Integer),
)

raw_sellers = sa.Table(
    "raw_sellers",
    Base.metadata,
    sa.Column("seller_id", sa.Text),
    sa.Column("seller_zip_code_prefix", sa.Integer),
    sa.Column("seller_city", sa.Text),
    sa.Column("seller_state", sa.Text),
)

raw_product_category_name_translation = sa.Table(
    "raw_product_category_name_translation",
    Base.metadata,
    sa.Column("product_category_name", sa.Text),
    sa.Column("product_category_name_english", sa.Text),
)

CSV_TO_TABLE: dict[str, sa.Table] = {
    "olist_customers_dataset.csv": raw_customers,
    "olist_geolocation_dataset.csv": raw_geolocation,
    "olist_order_items_dataset.csv": raw_order_items,
    "olist_order_payments_dataset.csv": raw_order_payments,
    "olist_order_reviews_dataset.csv": raw_order_reviews,
    "olist_orders_dataset.csv": raw_orders,
    "olist_products_dataset.csv": raw_products,
    "olist_sellers_dataset.csv": raw_sellers,
    "product_category_name_translation.csv": raw_product_category_name_translation,
}
