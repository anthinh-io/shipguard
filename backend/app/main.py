from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, dashboard, health, users
from app.core.config import settings

app = FastAPI(
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
