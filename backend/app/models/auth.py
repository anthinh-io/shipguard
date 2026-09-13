from typing import Literal

import sqlalchemy as sa

from app.core.db import Base

Role = Literal["operations_staff", "logistics_manager", "super_admin"]

# timezone=True an toàn ở đây: cảnh báo trong README chỉ áp cho các cột sinh tự động của
# orders, nơi phép ép kiểu timestamptz -> date không IMMUTABLE.
users = sa.Table(
    "users",
    Base.metadata,
    sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
    # Luôn ghi dạng chữ thường — xem normalize_email.
    sa.Column("email", sa.Text, nullable=False),
    sa.Column("display_name", sa.Text, nullable=False),
    sa.Column("password_hash", sa.Text, nullable=False),
    sa.Column("role", sa.Text, nullable=False),
    sa.Column("is_locked", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.CheckConstraint(
        "role IN ('operations_staff', 'logistics_manager', 'super_admin')",
        name="ck_users_role",
    ),
    sa.CheckConstraint(
        "btrim(display_name) <> ''", name="ck_users_display_name_not_blank"
    ),
)

# Chuẩn hoá ở mã chưa đủ: chỉ mục trên lower(email) chặn cả dòng chèn tay khác hoa thường.
sa.Index("uq_users_email_lower", sa.func.lower(users.c.email), unique=True)

# Đúng một Super Admin, bảo đảm ở cơ sở dữ liệu chứ không chỉ ở ensure_super_admin.
sa.Index(
    "uq_users_single_super_admin",
    users.c.role,
    unique=True,
    postgresql_where=users.c.role == "super_admin",
)

refresh_tokens = sa.Table(
    "refresh_tokens",
    Base.metadata,
    sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
    sa.Column(
        "user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False, index=True
    ),
    # SHA-256 chứ không Argon2: chuỗi ngẫu nhiên đã đủ entropy, và phải tra được theo
    # giá trị băm — Argon2 có muối nên cùng một chuỗi cho ra băm khác nhau.
    sa.Column("token_hash", sa.Text, nullable=False, unique=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("revoked_at", sa.DateTime(timezone=True)),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
)

# User Claim theo CONTEXT.md: quyền lẻ cộng thêm vào vai trò, một chuỗi mỗi dòng, ví dụ
# "orders:export". Chưa có danh mục claim hợp lệ — danh mục đó sinh ra cùng endpoint đầu
# tiên thật sự kiểm claim.
user_claims = sa.Table(
    "user_claims",
    Base.metadata,
    sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id"), primary_key=True),
    sa.Column("claim", sa.Text, primary_key=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.CheckConstraint("btrim(claim) <> ''", name="ck_user_claims_claim_not_blank"),
)
