from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import SessionDep

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["connected", "disconnected"]


@router.get("/health", response_model=HealthResponse)
async def health(response: Response, session: SessionDep) -> HealthResponse:
    try:
        await session.execute(text("SELECT 1"))
    # Deliberately broad: the try block holds one statement, and every way it
    # can fail means the database is unusable. Narrower clauses let real
    # failures through as 500 — a refused connection arrives as OSError from
    # asyncio and bad credentials as a raw asyncpg error, neither of them a
    # SQLAlchemyError.
    except Exception:
        response.status_code = 503
        return HealthResponse(status="degraded", database="disconnected")
    return HealthResponse(status="ok", database="connected")
