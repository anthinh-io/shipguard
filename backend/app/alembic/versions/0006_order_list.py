"""order value and lookup indexes for the order list

Revision ID: 0006_order_list
Revises: 0005_auth_tables
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_order_list"
down_revision: str | None = "0005_auth_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("order_value", sa.Numeric(12, 2), nullable=True))
    op.create_index("ix_orders_purchased_at", "orders", ["purchased_at"])
    op.create_index(
        "ix_orders_order_id_prefix",
        "orders",
        [sa.text("lower(order_id) text_pattern_ops")],
    )


def downgrade() -> None:
    op.drop_index("ix_orders_order_id_prefix", table_name="orders")
    op.drop_index("ix_orders_purchased_at", table_name="orders")
    op.drop_column("orders", "order_value")
