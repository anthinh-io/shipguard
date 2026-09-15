import sqlalchemy as sa

from app.core.db import Base

# Internal Note theo CONTEXT.md: chỉ thêm được, không sửa hay xóa. Đây là bảng nghiệp vụ,
# không phải bảng dẫn xuất — dựng lại dữ liệu đơn hàng không đụng tới nó.
order_notes = sa.Table(
    "order_notes",
    Base.metadata,
    sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
    # Cố ý không có khoá ngoại tới orders: build_derived_data TRUNCATE rồi dựng lại bảng
    # đó, nên khoá ngoại sẽ chặn bước dựng, hoặc xóa lan mọi ghi chú nếu thêm CASCADE.
    # Tầng dịch vụ tự kiểm đơn tồn tại khi thêm ghi chú.
    sa.Column("order_id", sa.Text, nullable=False),
    sa.Column("author_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
    sa.Column("body", sa.Text, nullable=False),
    # Mốc thật có múi giờ, không theo quy ước UTC không múi giờ của dữ liệu Olist.
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.CheckConstraint(
        "char_length(body) BETWEEN 1 AND 2000", name="ck_order_notes_body_length"
    ),
)

sa.Index(
    "ix_order_notes_order_id_created_at", order_notes.c.order_id, order_notes.c.created_at
)
