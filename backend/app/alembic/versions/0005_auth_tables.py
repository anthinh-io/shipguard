"""users, refresh tokens and user claims

Revision ID: 0005_auth_tables
Revises: 0004_sellers_table
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_auth_tables"
down_revision: str | None = "0004_sellers_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "is_locked", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('operations_staff', 'logistics_manager', 'super_admin')",
            name="ck_users_role",
        ),
        sa.CheckConstraint(
            "btrim(display_name) <> ''", name="ck_users_display_name_not_blank"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True
    )
    op.create_index(
        "uq_users_single_super_admin",
        "users",
        ["role"],
        unique=True,
        postgresql_where=sa.text("role = 'super_admin'"),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table(
        "user_claims",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("btrim(claim) <> ''", name="ck_user_claims_claim_not_blank"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id", "claim"),
    )


def downgrade() -> None:
    op.drop_table("user_claims")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("uq_users_single_super_admin", table_name="users")
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_table("users")
