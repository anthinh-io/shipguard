"""Đọc báo cáo huấn luyện và cộng dồn kết quả đối chiếu — CONTEXT.md, mục Reconciliation.

Hai phần độc lập với nhau: báo cáo là một tệp tĩnh do lệnh huấn luyện ghi ra, còn đối chiếu
đọc thẳng risk_assessments. Chưa huấn luyện lần nào không chặn phần đối chiếu — đó là hai
nguồn khác nhau, không phải một nguồn có hai cách đọc.
"""

import json
from pathlib import Path

import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.risk import risk_assessments
from app.risk.predictor import CHECKPOINTS
from app.risk.training import REPORT_FILENAME
from app.services.dashboard import is_small_sample


class CheckpointMetrics(BaseModel):
    precision: float
    recall: float
    f1: float


class AlgorithmReport(BaseModel):
    order_placed: CheckpointMetrics
    payment_approved: CheckpointMetrics
    handed_to_carrier: CheckpointMetrics


class TrainingReport(BaseModel):
    model_version: str
    trained_at: str
    selected_algorithm: str
    f1_target: float
    f1_at_order_placed: float
    meets_f1_target: bool
    algorithms: dict[str, AlgorithmReport]


class ReconciliationCheckpoint(BaseModel):
    checkpoint: str
    total: int
    correct: int
    incorrect: int
    precision: float | None
    recall: float | None
    small_sample: bool


def read_training_report(model_dir: Path) -> TrainingReport | None:
    """None khi lệnh huấn luyện chưa chạy lần nào — không phải một lỗi để ném ra."""
    report_path = Path(model_dir) / REPORT_FILENAME
    if not report_path.exists():
        return None
    raw = json.loads(report_path.read_text(encoding="utf-8"))
    algorithms = {
        name: AlgorithmReport(
            **{
                checkpoint: CheckpointMetrics(
                    **evaluation["test"][checkpoint]["at_selected_threshold"]
                )
                for checkpoint in CHECKPOINTS
            }
        )
        for name, evaluation in raw["algorithms"].items()
    }
    return TrainingReport(
        model_version=raw["model_version"],
        trained_at=raw["trained_at"],
        selected_algorithm=raw["selected_algorithm"],
        f1_target=raw["f1_target"],
        f1_at_order_placed=raw["f1_at_order_placed"],
        meets_f1_target=raw["meets_f1_target"],
        algorithms=algorithms,
    )


async def compute_reconciliation(session: AsyncSession) -> list[ReconciliationCheckpoint]:
    """Cộng dồn was_correct theo từng mốc dự đoán.

    Đơn hủy hoặc chưa giao không cần lọc riêng: was_correct chỉ được ghi khi ghi nhận mốc
    delivered_to_customer (order_lifecycle.record_milestone), mà đơn đã hủy không bao giờ
    nhận được mốc đó — WHERE was_correct IS NOT NULL đã tự loại cả hai trường hợp.
    """
    rows = (
        await session.execute(
            sa.select(
                risk_assessments.c.checkpoint,
                risk_assessments.c.is_high_risk,
                risk_assessments.c.was_correct,
                sa.func.count().label("n"),
            )
            .where(risk_assessments.c.was_correct.is_not(None))
            .group_by(
                risk_assessments.c.checkpoint,
                risk_assessments.c.is_high_risk,
                risk_assessments.c.was_correct,
            )
        )
    ).all()

    buckets: dict[str, dict[tuple[bool, bool], int]] = {
        checkpoint: {} for checkpoint in CHECKPOINTS
    }
    for row in rows:
        buckets.setdefault(row.checkpoint, {})[(row.is_high_risk, row.was_correct)] = row.n

    results = []
    for checkpoint in CHECKPOINTS:
        counts = buckets.get(checkpoint, {})
        tp = counts.get((True, True), 0)
        fp = counts.get((True, False), 0)
        fn = counts.get((False, False), 0)
        tn = counts.get((False, True), 0)
        total = tp + fp + fn + tn
        results.append(
            ReconciliationCheckpoint(
                checkpoint=checkpoint,
                total=total,
                correct=tp + tn,
                incorrect=fp + fn,
                precision=tp / (tp + fp) if (tp + fp) > 0 else None,
                recall=tp / (tp + fn) if (tp + fn) > 0 else None,
                small_sample=is_small_sample(total),
            )
        )
    return results
