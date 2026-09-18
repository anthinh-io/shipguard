import logging
from collections.abc import AsyncIterator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.security import CurrentUser, decode_access_token
from app.risk.predictor import RiskPredictor, load_predictor

logger = logging.getLogger(__name__)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db)]


# Bộ dự đoán là một dependency, không phải biến toàn cục nạp trong lifespan: httpx
# ASGITransport không chạy lifespan, nên một biến toàn cục sẽ rỗng ở mọi bài test và
# không có cách nào thay bằng bản giả. Cùng vai trò với get_db ở trên — một điểm nối
# mà dependency_overrides thay được — dù nó đồng bộ và không cần dọn dẹp sau khi dùng.
def get_predictor() -> RiskPredictor:
    # Bắt rộng chứ không riêng FileNotFoundError: một lần huấn luyện bị ngắt giữa
    # chừng để lại tệp .joblib viết dở, và một tệp ghi bằng phiên bản thư viện khác
    # cũng ném lỗi kiểu khác. Cả hai đều là "mô hình không dùng được" chứ không phải
    # "backend hỏng", nên 503 chứ không phải 500.
    try:
        return load_predictor(settings.RISK_MODEL_DIR)
    except Exception:
        logger.warning(
            "Không nạp được mô hình rủi ro từ %s", settings.RISK_MODEL_DIR, exc_info=True
        )
        raise HTTPException(
            status_code=503, detail="Risk model is not available"
        ) from None


PredictorDep = Annotated[RiskPredictor, Depends(get_predictor)]

# auto_error=False để mọi kiểu thiếu phiên — không header, sai scheme, token hỏng — đi
# qua cùng một nhánh 401 bên dưới thay vì dựa vào mã lỗi mặc định của HTTPBearer.
bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> CurrentUser:
    unauthorized = HTTPException(
        status_code=401,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        return decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError:
        raise unauthorized from None


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]

USER_ADMIN_ROLES = ("logistics_manager", "super_admin")


# Vai trò đọc từ token (ADR-0006): người vừa bị hạ vai trò vẫn qua được cửa này tối đa
# 15 phút, cho tới khi access token hết hạn và refresh token đã bị thu hồi.
async def require_user_admin(current_user: CurrentUserDep) -> CurrentUser:
    if current_user.role not in USER_ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Not allowed to manage users")
    return current_user


UserAdminDep = Annotated[CurrentUser, Depends(require_user_admin)]
