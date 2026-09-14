from collections.abc import AsyncIterator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.core.security import CurrentUser, decode_access_token


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db)]

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
