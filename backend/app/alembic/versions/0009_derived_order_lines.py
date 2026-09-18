"""derived product lines, payment lines, reviews and the category lookup

Revision ID: 0009_derived_order_lines
Revises: 0008_order_notes
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_derived_order_lines"
down_revision: str | None = "0008_order_notes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Ba bảng gắn với đơn có khoá ngoại tới orders, khác order_notes: chúng được truncate và
    # dựng lại cùng một lượt với orders, đúng như order_sellers, nên khoá ngoại không chặn
    # bước dựng mà còn bắt được dòng mồ côi.
    #
    # Không bảng nào cần chỉ mục order_id riêng: khoá chính ghép đã mở đầu bằng order_id,
    # cùng lý do với order_sellers.
    op.create_table(
        "order_items",
        sa.Column("order_id", sa.Text(), nullable=False),
        sa.Column("order_item_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Text(), nullable=False),
        # Tên danh mục gốc tiếng Bồ, không phải nhãn tiếng Anh: nhãn tra ở product_categories
        # lúc đọc. 1.603 dòng không có danh mục nào nên cột để trống được.
        sa.Column("product_category_name", sa.Text(), nullable=True),
        # Mô hình dự đoán cần cân nặng; trang chi tiết đơn không hiện nó. 18 dòng để trống.
        sa.Column("product_weight_g", sa.Integer(), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("freight_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("seller_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.order_id"]),
        sa.PrimaryKeyConstraint("order_id", "order_item_id"),
    )

    op.create_table(
        "order_payments",
        sa.Column("order_id", sa.Text(), nullable=False),
        sa.Column("payment_sequential", sa.Integer(), nullable=False),
        sa.Column("payment_type", sa.Text(), nullable=False),
        sa.Column("payment_installments", sa.Integer(), nullable=False),
        sa.Column("payment_value", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.order_id"]),
        sa.PrimaryKeyConstraint("order_id", "payment_sequential"),
    )

    # review_sequential là thứ tự đánh giá trong một đơn, gán lúc dựng. Bắt buộc phải có:
    # dữ liệu Olist có 99.224 dòng đánh giá trên 98.673 mã đơn — 547 đơn có 2–3 đánh giá,
    # nên một mình order_id không làm khoá chính được. Nó cũng đóng cứng một thứ tự đọc cố
    # định: 157 cặp (order_id, review_creation_date) trùng nhau, nên sắp theo riêng thời
    # điểm tạo là bất định.
    op.create_table(
        "order_reviews",
        sa.Column("order_id", sa.Text(), nullable=False),
        sa.Column("review_sequential", sa.Integer(), nullable=False),
        sa.Column("review_score", sa.SmallInteger(), nullable=False),
        sa.Column("comment_title", sa.Text(), nullable=True),
        sa.Column("comment_message", sa.Text(), nullable=True),
        # Không timezone: mọi dấu thời gian của dữ liệu đơn đều không múi giờ — xem
        # app/models/derived.py. order_notes.created_at là ngoại lệ có chủ đích, đừng lẫn.
        sa.Column("review_created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.order_id"]),
        sa.PrimaryKeyConstraint("order_id", "review_sequential"),
    )

    # Bảng tra danh mục không gắn với đơn nên không có khoá ngoại nào. Nó là nguồn nhãn
    # tiếng Anh cho trang chi tiết, và là nguồn ô chọn danh mục của biểu mẫu tạo đơn.
    op.create_table(
        "product_categories",
        sa.Column("product_category_name", sa.Text(), nullable=False),
        sa.Column("product_category_name_english", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("product_category_name"),
    )


def downgrade() -> None:
    op.drop_table("product_categories")
    op.drop_table("order_reviews")
    op.drop_table("order_payments")
    op.drop_table("order_items")
