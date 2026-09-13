from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, HTTPException, Response, status
from pydantic import BaseModel

from app.api.deps import SessionDep
from app.core.security import REFRESH_TOKEN_TTL, create_access_token
from app.services.auth import (
    authenticate,
    issue_refresh_token,
    load_claims,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
# Cookie chỉ đi kèm /auth/*, không đi theo mọi lời gọi API. Chưa đặt Secure vì môi trường
# phát triển chạy http — phải xem lại khi triển khai HTTPS (ADR-0006).
REFRESH_COOKIE_ATTRIBUTES = {"httponly": True, "samesite": "lax", "path": "/auth"}


class LoginRequest(BaseModel):
    # Cố ý không có ràng buộc độ dài hay định dạng: một 422 riêng cho mật khẩu ngắn là
    # tín hiệu dò khác với thông báo đăng nhập thất bại chung.
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


def set_refresh_cookie(response: Response, raw: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        raw,
        max_age=int(REFRESH_TOKEN_TTL.total_seconds()),
        **REFRESH_COOKIE_ATTRIBUTES,
    )


@router.post("/login")
async def login(
    body: LoginRequest, response: Response, session: SessionDep
) -> TokenResponse:
    user = await authenticate(session, body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    claims = await load_claims(session, user.id)
    set_refresh_cookie(response, await issue_refresh_token(session, user.id))
    return TokenResponse(access_token=create_access_token(user.id, user.role, claims))


@router.post("/refresh")
async def refresh(
    response: Response,
    session: SessionDep,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> TokenResponse:
    rotated = (
        None
        if refresh_token is None
        else await rotate_refresh_token(session, refresh_token)
    )
    if rotated is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    user, new_raw = rotated
    claims = await load_claims(session, user.id)
    set_refresh_cookie(response, new_raw)
    return TokenResponse(access_token=create_access_token(user.id, user.role, claims))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session: SessionDep,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> None:
    if refresh_token is not None:
        await revoke_refresh_token(session, refresh_token)
    # Xóa phải cùng path với lúc đặt, nếu không trình duyệt giữ nguyên cookie cũ.
    response.delete_cookie(REFRESH_COOKIE, **REFRESH_COOKIE_ATTRIBUTES)
