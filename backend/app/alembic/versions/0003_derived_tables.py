"""derived order tables

Revision ID: 0003_derived_tables
Revises: 0002_raw_tables
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_derived_tables"
down_revision: str | None = "0002_raw_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("order_id", sa.Text(), nullable=False),
        sa.Column("order_status", sa.Text(), nullable=False),
        sa.Column("customer_state", sa.Text(), nullable=False),
        sa.Column("purchased_at", sa.DateTime(), nullable=False),
        sa.Column("payment_approved_at", sa.DateTime(), nullable=True),
        sa.Column("handed_to_carrier_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_to_customer_at", sa.DateTime(), nullable=True),
        sa.Column("estimated_delivery_date", sa.Date(), nullable=False),
        sa.Column("worst_review_score", sa.SmallInteger(), nullable=True),
        sa.Column(
            "payment_approval",
            sa.Interval(),
            sa.Computed("payment_approved_at - purchased_at", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "seller_handling",
            sa.Interval(),
            sa.Computed("handed_to_carrier_at - payment_approved_at", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "carrier_transit",
            sa.Interval(),
            sa.Computed(
                "delivered_to_customer_at - handed_to_carrier_at", persisted=True
            ),
            nullable=True,
        ),
        sa.Column(
            "is_late",
            sa.Boolean(),
            sa.Computed(
                "delivered_to_customer_at::date > estimated_delivery_date",
                persisted=True,
            ),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("order_id"),
    )
    op.create_index(
        "ix_orders_delivered_to_customer_at", "orders", ["delivered_to_customer_at"]
    )
    op.create_index("ix_orders_customer_state", "orders", ["customer_state"])
    op.create_table(
        "order_sellers",
        sa.Column("order_id", sa.Text(), nullable=False),
        sa.Column("seller_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.order_id"]),
        sa.PrimaryKeyConstraint("order_id", "seller_id"),
    )
    op.create_index("ix_order_sellers_seller_id", "order_sellers", ["seller_id"])


def downgrade() -> None:
    op.drop_index("ix_order_sellers_seller_id", table_name="order_sellers")
    op.drop_table("order_sellers")
    op.drop_index("ix_orders_customer_state", table_name="orders")
    op.drop_index("ix_orders_delivered_to_customer_at", table_name="orders")
    op.drop_table("orders")
