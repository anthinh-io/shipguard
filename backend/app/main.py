import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, dashboard, health, orders, users
from app.core.config import settings
from app.core.db import SessionLocal
from app.risk.predictor import load_predictor
from app.services.users import ensure_super_admin

logger = logging.getLogger(__name__)


def warm_risk_predictor() -> None:
    """Nạp trước bộ mô hình để lần dự đoán đầu tiên không phải chờ đọc tệp.

    Nuốt lỗi ở đây là có chủ đích, và khác hẳn quy tắc của ensure_super_admin ngay bên
    dưới: thiếu tài khoản quản trị thì dừng hẳn máy chủ, còn thiếu tệp mô hình thì
    bảng điều khiển và tra cứu đơn vẫn phải dùng được. Chỉ thao tác cần dự đoán mới
    báo lỗi, và chỗ báo là get_predictor.
    """
    try:
        load_predictor(settings.RISK_MODEL_DIR)
    except Exception:
        logger.warning(
            "Chưa nạp được mô hình rủi ro từ %s; các thao tác cần dự đoán sẽ báo lỗi. "
            "Chạy: uv run python -m app.scripts.train_risk_model",
            settings.RISK_MODEL_DIR,
        )


# Lỗi ở đây để nguyên cho uvicorn in ra và dừng: backend chạy mà không có lối vào nào
# còn tệ hơn không chạy. Logic nằm ở ensure_super_admin để test gọi thẳng được — httpx
# ASGITransport không chạy lifespan.
@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with SessionLocal() as session:
        await ensure_super_admin(
            session,
            email=settings.SUPER_ADMIN_EMAIL,
            password=settings.SUPER_ADMIN_PASSWORD,
            display_name=settings.SUPER_ADMIN_NAME,
        )
    warm_risk_predictor()
    yield


app = FastAPI(
    lifespan=lifespan,
    title=settings.PROJECT_NAME,
    description=(
        "A web application for managing and predicting delivery performance in "
        "logistics, powered by ML models trained on the Olist Brazilian E-Commerce "
        "dataset."
    ),
)

# Trình duyệt gọi thẳng backend có xác thực — xem ADR-0006. allow_credentials để cookie
# refresh token đi kèm /auth/*; header Authorization gây preflight nên phải mở tường minh.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)

# Mọi route yêu cầu access token trừ /health và /auth/* (ADR-0006) — /auth/logout cũng
# mở, vì nó chỉ cần cookie refresh token.
app.include_router(health.router)
app.include_router(dashboard.router)
app.include_router(orders.router)
app.include_router(auth.router)
app.include_router(users.router)
