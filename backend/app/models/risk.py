import sqlalchemy as sa

from app.core.db import Base

# Một lần hệ thống đánh giá khả năng giao trễ của một đơn — CONTEXT.md, mục Risk Assessment.
#
# Không có khoá ngoại tới orders, giống order_notes nhưng vì một lý do mạnh hơn: chính bảng
# này là thứ chặn build_derived_data (ADR-0007 việc 3, ADR-0010 việc 4) — sự tồn tại của ít
# nhất một dòng ở đây là dấu hiệu duy nhất phân biệt đơn tạo trong Ship Guard với đơn Olist
# lịch sử còn dang dở. Tầng dịch vụ tự kiểm đơn tồn tại khi tạo đánh giá.
#
# Dựng đủ ba phần ngay từ #31 — đánh giá, xử lý (#35), đối chiếu (#33) — để hai ticket sau
# không mỗi ticket viết một migration rồi đụng nhau. Cột của hai ticket đó để trống ở đây.
risk_assessments = sa.Table(
    "risk_assessments",
    Base.metadata,
    sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
    sa.Column("order_id", sa.Text, nullable=False),
    sa.Column("checkpoint", sa.Text, nullable=False),
    # Mốc thật lúc hệ thống chấm điểm — có múi giờ, khác quy ước không múi giờ của các mốc
    # đơn. Cùng loại với order_notes.created_at.
    sa.Column(
        "assessed_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Column("late_probability", sa.Float, nullable=False),
    # Mức rủi ro chốt ngay lúc đánh giá — đổi RISK_THRESHOLD về sau không xếp lại các lần
    # cũ, nên ngưỡng đã dùng lưu cùng bản ghi ở threshold_used bên dưới.
    sa.Column("is_high_risk", sa.Boolean, nullable=False),
    sa.Column("threshold_used", sa.Float, nullable=False),
    sa.Column("model_version", sa.Text, nullable=False),
    sa.Column("risk_cause_stage", sa.Text, nullable=False),
    # Chỉ có giá trị khi nguyên nhân là khâu người bán.
    sa.Column("risk_cause_seller_id", sa.Text),
    # Trung vị dự kiến và trung vị lịch sử của từng chặng CHƯA xong. Chặng đã xong tại mốc
    # đánh giá thì cặp cột của nó để trống.
    sa.Column("payment_approval_median_days", sa.Float),
    sa.Column("payment_approval_historical_median_days", sa.Float),
    sa.Column("seller_handling_median_days", sa.Float),
    sa.Column("seller_handling_historical_median_days", sa.Float),
    sa.Column("carrier_transit_median_days", sa.Float),
    sa.Column("carrier_transit_historical_median_days", sa.Float),
    sa.Column("created_by", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
    # Phần xử lý — #35.
    sa.Column("intervention", sa.Text),
    sa.Column("intervention_note", sa.Text),
    sa.Column("handled_by", sa.BigInteger, sa.ForeignKey("users.id")),
    sa.Column("handled_at", sa.DateTime(timezone=True)),
    # Phần đối chiếu — #33.
    sa.Column("was_correct", sa.Boolean),
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

sa.Index(
    "ix_risk_assessments_order_id_assessed_at",
    risk_assessments.c.order_id,
    risk_assessments.c.assessed_at,
)
