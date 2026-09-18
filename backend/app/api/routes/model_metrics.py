from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import SessionDep, get_current_user
from app.core.config import settings
from app.services.model_metrics import (
    ReconciliationCheckpoint,
    TrainingReport,
    compute_reconciliation,
    read_training_report,
)

# Khóa ở mức router chứ không gắn vào từng handler, giống dashboard.py: trang chỉ số chỉ
# cần biết là đã đăng nhập, không cần biết vai trò — mọi vai trò đều xem được (CONTEXT.md).
router = APIRouter(tags=["model-metrics"], dependencies=[Depends(get_current_user)])


class ModelMetricsResponse(BaseModel):
    # False khi lệnh huấn luyện chưa chạy lần nào — report khi đó là None, còn
    # reconciliation vẫn tính được vì nó đọc risk_assessments, không đọc report.
    trained: bool
    report: TrainingReport | None
    risk_threshold: float
    reconciliation: list[ReconciliationCheckpoint]


@router.get("/model-metrics", response_model=ModelMetricsResponse)
async def model_metrics(session: SessionDep) -> ModelMetricsResponse:
    report = read_training_report(settings.RISK_MODEL_DIR)
    return ModelMetricsResponse(
        trained=report is not None,
        report=report,
        risk_threshold=settings.RISK_THRESHOLD,
        reconciliation=await compute_reconciliation(session),
    )
