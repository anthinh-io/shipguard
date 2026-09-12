from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import SessionDep
from app.services.dashboard import (
    DashboardKpis,
    LateRateTrend,
    ReportingPeriod,
    StateLateRate,
    compute_kpis,
    compute_late_rate_by_state,
    compute_late_rate_trend,
    resolve_default_period,
)

router = APIRouter(tags=["dashboard"])


# Một endpoint tổng hợp nhận mọi điều kiện lọc và trả mọi số liệu của bảng điều khiển
# trong một lần gọi. "Một lần gọi" ở đây là một lần gọi HTTP, không phải một câu SQL:
# route chạy nhiều truy vấn (giải kỳ, rồi tính từng khối) và như vậy là đúng. Mỗi khối
# lồng riêng để các chỉ số về sau nối thêm mà không phải đổi hình dạng phản hồi.
class DashboardResponse(BaseModel):
    reporting_period: ReportingPeriod | None
    kpis: DashboardKpis
    late_rate_trend: LateRateTrend
    late_rate_by_state: list[StateLateRate]


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    session: SessionDep,
    start_date: date | None = None,
    end_date: date | None = None,
) -> DashboardResponse:
    if (start_date is None) != (end_date is None):
        raise HTTPException(
            status_code=422,
            detail="start_date and end_date must be given together, or both omitted",
        )

    period = (
        ReportingPeriod(start_date=start_date, end_date=end_date)
        if start_date is not None and end_date is not None
        else await resolve_default_period(session)
    )
    return DashboardResponse(
        reporting_period=period,
        kpis=await compute_kpis(session, period),
        late_rate_trend=await compute_late_rate_trend(session, period),
        late_rate_by_state=await compute_late_rate_by_state(session, period),
    )
