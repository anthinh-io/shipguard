from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUserDep, SessionDep
from app.core.security import REFRESH_TOKEN_TTL, create_access_token
from app.services.auth import (
    authenticate,
    issue_refresh_token,
    load_claims,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.services.users import (
    PasswordTooShortError,
    WrongCurrentPasswordError,
    change_password,
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


class ChangePasswordRequest(BaseModel):
    # Không đặt min_length ở đây: độ dài do check_password_policy quyết, một chỗ duy nhất
    # dùng chung với tạo User và script đặt lại mật khẩu.
    current_password: str
    new_password: str


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


async def token_response(
    response: Response, session: AsyncSession, user: Row, refresh_token: str
) -> TokenResponse:
    # Claim đọc ngay lúc cấp token, nên claim mới gán có hiệu lực từ lần làm mới kế tiếp.
    claims = await load_claims(session, user.id)
    set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=create_access_token(user.id, user.role, claims))


@router.post("/login")
async def login(
    body: LoginRequest, response: Response, session: SessionDep
) -> TokenResponse:
    user = await authenticate(session, body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return await token_response(
        response, session, user, await issue_refresh_token(session, user.id)
    )


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
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user, rotated_refresh_token = rotated
    return await token_response(response, session, user, rotated_refresh_token)


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    session: SessionDep,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> None:
    if refresh_token is not None:
        await revoke_refresh_token(session, refresh_token)
    # Xóa phải cùng path với lúc đặt, nếu không trình duyệt giữ nguyên cookie cũ.
    response.delete_cookie(REFRESH_COOKIE, **REFRESH_COOKIE_ATTRIBUTES)


# Router /auth không gắn get_current_user ở mức router (login, refresh, logout chạy khi
# chưa có access token), nên route này phải tự khai.
@router.post("/password")
async def change_own_password(
    body: ChangePasswordRequest,
    response: Response,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> TokenResponse:
    try:
        user = await change_password(
            session, current_user.user_id, body.current_password, body.new_password
        )
    except PasswordTooShortError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except WrongCurrentPasswordError as error:
        # 400 chứ không 401: frontend hiểu 401 là phiên hết hạn và đá người dùng ra. Báo
        # rõ từng lý do — khác /auth/login — vì người gọi đã chứng minh danh tính.
        raise HTTPException(status_code=400, detail=str(error)) from None
    return await token_response(
        response, session, user, await issue_refresh_token(session, user.id)
    )
