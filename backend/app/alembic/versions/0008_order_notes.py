"""internal notes on orders

Revision ID: 0008_order_notes
Revises: 0007_order_detail
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_order_notes"
down_revision: str | None = "0007_order_detail"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "order_notes",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        # Không có khoá ngoại tới orders: build_derived_data TRUNCATE rồi dựng lại bảng đó.
        sa.Column("order_id", sa.Text(), nullable=False),
        sa.Column("author_id", sa.BigInteger(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        # User không bao giờ bị xóa, chỉ bị khóa — khoá ngoại này không chặn gì.
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.CheckConstraint(
            "char_length(body) BETWEEN 1 AND 2000", name="ck_order_notes_body_length"
        ),
    )
    op.create_index(
        "ix_order_notes_order_id_created_at", "order_notes", ["order_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_order_notes_order_id_created_at", table_name="order_notes")
    op.drop_table("order_notes")
