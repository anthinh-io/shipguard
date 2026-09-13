from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, dashboard, health, users
from app.core.config import settings
from app.core.db import SessionLocal
from app.services.users import ensure_super_admin


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

app.include_router(health.router)
# /dashboard và /sellers chưa gắn CurrentUserDep: khóa chúng đi cùng cổng đăng nhập phía
# trình duyệt ở ticket sau, nếu không bảng điều khiển đang chạy sẽ hỏng.
app.include_router(dashboard.router)
app.include_router(auth.router)
app.include_router(users.router)
