"""derived sellers table

Revision ID: 0004_sellers_table
Revises: 0003_derived_tables
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_sellers_table"
down_revision: str | None = "0003_derived_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Không có chỉ mục nào: bảng chỉ vài nghìn dòng, và truy vấn gợi ý khớp tiền tố
    # trên ba cột cùng lúc bằng ILIKE — quét tuần tự rẻ hơn mọi chỉ mục dựng cho nó.
    op.create_table(
        "sellers",
        sa.Column("seller_id", sa.Text(), nullable=False),
        sa.Column("seller_city", sa.Text(), nullable=False),
        sa.Column("seller_state", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("seller_id"),
    )


def downgrade() -> None:
    op.drop_table("sellers")
