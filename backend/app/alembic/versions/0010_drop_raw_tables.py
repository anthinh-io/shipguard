"""drop the nine raw olist tables

Revision ID: 0010_drop_raw_tables
Revises: 0009_derived_order_lines
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_drop_raw_tables"
down_revision: str | None = "0009_derived_order_lines"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Ba chỉ mục ix_raw_* của 0007 rơi theo bảng, không cần drop_index riêng.
    # Không bảng nào có khoá ngoại nên thứ tự xoá không quan trọng.
    op.drop_table("raw_sellers")
    op.drop_table("raw_products")
    op.drop_table("raw_product_category_name_translation")
    op.drop_table("raw_orders")
    op.drop_table("raw_order_reviews")
    op.drop_table("raw_order_payments")
    op.drop_table("raw_order_items")
    op.drop_table("raw_geolocation")
    op.drop_table("raw_customers")


def downgrade() -> None:
    # Dựng lại y nguyên lược đồ của 0002 cộng ba chỉ mục của 0007. Chín bảng quay về
    # rỗng: dữ liệu vốn nằm ở tệp CSV trong datasets/raw, nạp lại được bất cứ lúc nào.
    op.create_table(
        "raw_customers",
        sa.Column("customer_id", sa.Text(), nullable=True),
        sa.Column("customer_unique_id", sa.Text(), nullable=True),
        sa.Column("customer_zip_code_prefix", sa.Integer(), nullable=True),
        sa.Column("customer_city", sa.Text(), nullable=True),
        sa.Column("customer_state", sa.Text(), nullable=True),
    )
    op.create_table(
        "raw_geolocation",
        sa.Column("geolocation_zip_code_prefix", sa.Integer(), nullable=True),
        sa.Column("geolocation_lat", sa.Double(), nullable=True),
        sa.Column("geolocation_lng", sa.Double(), nullable=True),
        sa.Column("geolocation_city", sa.Text(), nullable=True),
        sa.Column("geolocation_state", sa.Text(), nullable=True),
    )
    op.create_table(
        "raw_order_items",
        sa.Column("order_id", sa.Text(), nullable=True),
        sa.Column("order_item_id", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Text(), nullable=True),
        sa.Column("seller_id", sa.Text(), nullable=True),
        sa.Column("shipping_limit_date", sa.DateTime(), nullable=True),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("freight_value", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.create_table(
        "raw_order_payments",
        sa.Column("order_id", sa.Text(), nullable=True),
        sa.Column("payment_sequential", sa.Integer(), nullable=True),
        sa.Column("payment_type", sa.Text(), nullable=True),
        sa.Column("payment_installments", sa.Integer(), nullable=True),
        sa.Column("payment_value", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.create_table(
        "raw_order_reviews",
        sa.Column("review_id", sa.Text(), nullable=True),
        sa.Column("order_id", sa.Text(), nullable=True),
        sa.Column("review_score", sa.Integer(), nullable=True),
        sa.Column("review_comment_title", sa.Text(), nullable=True),
        sa.Column("review_comment_message", sa.Text(), nullable=True),
        sa.Column("review_creation_date", sa.DateTime(), nullable=True),
        sa.Column("review_answer_timestamp", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "raw_orders",
        sa.Column("order_id", sa.Text(), nullable=True),
        sa.Column("customer_id", sa.Text(), nullable=True),
        sa.Column("order_status", sa.Text(), nullable=True),
        sa.Column("order_purchase_timestamp", sa.DateTime(), nullable=True),
        sa.Column("order_approved_at", sa.DateTime(), nullable=True),
        sa.Column("order_delivered_carrier_date", sa.DateTime(), nullable=True),
        sa.Column("order_delivered_customer_date", sa.DateTime(), nullable=True),
        sa.Column("order_estimated_delivery_date", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "raw_product_category_name_translation",
        sa.Column("product_category_name", sa.Text(), nullable=True),
        sa.Column("product_category_name_english", sa.Text(), nullable=True),
    )
    op.create_table(
        "raw_products",
        sa.Column("product_id", sa.Text(), nullable=True),
        sa.Column("product_category_name", sa.Text(), nullable=True),
        sa.Column("product_name_lenght", sa.Integer(), nullable=True),
        sa.Column("product_description_lenght", sa.Integer(), nullable=True),
        sa.Column("product_photos_qty", sa.Integer(), nullable=True),
        sa.Column("product_weight_g", sa.Integer(), nullable=True),
        sa.Column("product_length_cm", sa.Integer(), nullable=True),
        sa.Column("product_height_cm", sa.Integer(), nullable=True),
        sa.Column("product_width_cm", sa.Integer(), nullable=True),
    )
    op.create_table(
        "raw_sellers",
        sa.Column("seller_id", sa.Text(), nullable=True),
        sa.Column("seller_zip_code_prefix", sa.Integer(), nullable=True),
        sa.Column("seller_city", sa.Text(), nullable=True),
        sa.Column("seller_state", sa.Text(), nullable=True),
    )
    op.create_index("ix_raw_order_items_order_id", "raw_order_items", ["order_id"])
    op.create_index("ix_raw_order_payments_order_id", "raw_order_payments", ["order_id"])
    op.create_index("ix_raw_order_reviews_order_id", "raw_order_reviews", ["order_id"])
