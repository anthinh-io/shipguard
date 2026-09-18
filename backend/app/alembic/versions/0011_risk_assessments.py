"""seller zip code prefix and the risk_assessments table

Revision ID: 0011_risk_assessments
Revises: 0010_drop_raw_tables
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_risk_assessments"
down_revision: str | None = "0010_drop_raw_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Cho phép NULL vì bảng đã có dữ liệu lúc thêm cột; build_derived_data điền lại. Kiểu
    # text chứ không phải số, cùng lý do với customer_zip_code_prefix: mã bưu chính giữ số 0
    # đầu, còn cột số nguyên đã làm mất nó ở lớp thô cũ.
    op.add_column("sellers", sa.Column("seller_zip_code_prefix", sa.Text(), nullable=True))

    # Không có khoá ngoại tới orders, giống order_notes nhưng vì một lý do mạnh hơn: chính
    # bảng này là thứ chặn build_derived_data (ADR-0007 việc 3, ADR-0010 việc 4), nên nó
    # phải sống sót độc lập với orders. Tầng dịch vụ tự kiểm đơn tồn tại.
    #
    # Dựng đủ ba phần ngay từ đầu — đánh giá, xử lý, đối chiếu — để #33 và #35 không mỗi
    # ticket viết một migration rồi đụng nhau. Cột của hai ticket đó để trống ở đây.
    op.create_table(
        "risk_assessments",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("order_id", sa.Text(), nullable=False),
        sa.Column("checkpoint", sa.Text(), nullable=False),
        # Mốc thật lúc hệ thống chấm điểm — có múi giờ, khác quy ước không múi giờ của các
        # mốc đơn. Cùng loại với order_notes.created_at.
        sa.Column(
            "assessed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("late_probability", sa.Float(), nullable=False),
        # Mức rủi ro chốt ngay lúc đánh giá — đổi RISK_THRESHOLD về sau không xếp lại các
        # lần cũ, nên ngưỡng đã dùng lưu cùng bản ghi ở cột threshold_used bên dưới.
        sa.Column("is_high_risk", sa.Boolean(), nullable=False),
        sa.Column("threshold_used", sa.Float(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("risk_cause_stage", sa.Text(), nullable=False),
        # Chỉ có giá trị khi nguyên nhân là khâu người bán.
        sa.Column("risk_cause_seller_id", sa.Text(), nullable=True),
        # Trung vị dự kiến và trung vị lịch sử của từng chặng CHƯA xong. Chặng đã xong tại
        # mốc đánh giá thì cặp cột của nó để trống.
        sa.Column("payment_approval_median_days", sa.Float(), nullable=True),
        sa.Column("payment_approval_historical_median_days", sa.Float(), nullable=True),
        sa.Column("seller_handling_median_days", sa.Float(), nullable=True),
        sa.Column("seller_handling_historical_median_days", sa.Float(), nullable=True),
        sa.Column("carrier_transit_median_days", sa.Float(), nullable=True),
        sa.Column("carrier_transit_historical_median_days", sa.Float(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        # Phần xử lý — #35.
        sa.Column("intervention", sa.Text(), nullable=True),
        sa.Column("intervention_note", sa.Text(), nullable=True),
        sa.Column("handled_by", sa.BigInteger(), nullable=True),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        # Phần đối chiếu — #33.
        sa.Column("was_correct", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        # User không bao giờ bị xóa, chỉ bị khóa — hai khoá ngoại này không chặn gì.
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["handled_by"], ["users.id"]),
        sa.CheckConstraint(
            "checkpoint IN ('order_placed', 'payment_approved', 'handed_to_carrier')",
            name="ck_risk_assessments_checkpoint",
        ),
        sa.CheckConstraint(
            "late_probability BETWEEN 0 AND 1", name="ck_risk_assessments_late_probability"
        ),
        sa.CheckConstraint(
            "threshold_used > 0 AND threshold_used < 1",
            name="ck_risk_assessments_threshold_used",
        ),
        sa.CheckConstraint(
            "risk_cause_stage IN ('payment_approval', 'seller_handling', 'carrier_transit')",
            name="ck_risk_assessments_risk_cause_stage",
        ),
        sa.CheckConstraint(
            "intervention IN "
            "('remind_seller', 'change_carrier', 'contact_payment', 'notify_customer', 'other')",
            name="ck_risk_assessments_intervention",
        ),
        sa.CheckConstraint(
            "char_length(intervention_note) <= 2000",
            name="ck_risk_assessments_intervention_note_length",
        ),
    )
    op.create_index(
        "ix_risk_assessments_order_id_assessed_at",
        "risk_assessments",
        ["order_id", "assessed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_risk_assessments_order_id_assessed_at", table_name="risk_assessments"
    )
    op.drop_table("risk_assessments")
    op.drop_column("sellers", "seller_zip_code_prefix")
