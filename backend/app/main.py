from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import dashboard, health
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

# Bảng điều khiển gọi thẳng backend từ trình duyệt — xem ADR-0002. Chỉ mở GET và không
# bật allow_credentials: không có phiên đăng nhập nào để mang theo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_methods=["GET"],
)

app.include_router(health.router)
app.include_router(dashboard.router)
