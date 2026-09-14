"""shipping address columns and order_id indexes for the order detail page

Revision ID: 0007_order_detail
Revises: 0006_order_list
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_order_detail"
down_revision: str | None = "0006_order_list"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Cho phép NULL vì bảng đã có dữ liệu lúc thêm cột; build_derived_data điền lại.
    op.add_column("orders", sa.Column("customer_city", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("customer_zip_code_prefix", sa.Text(), nullable=True))
    op.create_index("ix_raw_order_items_order_id", "raw_order_items", ["order_id"])
    op.create_index("ix_raw_order_payments_order_id", "raw_order_payments", ["order_id"])
    op.create_index("ix_raw_order_reviews_order_id", "raw_order_reviews", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_raw_order_reviews_order_id", table_name="raw_order_reviews")
    op.drop_index("ix_raw_order_payments_order_id", table_name="raw_order_payments")
    op.drop_index("ix_raw_order_items_order_id", table_name="raw_order_items")
    op.drop_column("orders", "customer_zip_code_prefix")
    op.drop_column("orders", "customer_city")
