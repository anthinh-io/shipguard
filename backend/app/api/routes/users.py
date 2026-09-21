from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, StringConstraints

from app.api.deps import CurrentUserDep, SessionDep, UserAdminDep
from app.services.users import (
    AssignableRole,
    EmailTakenError,
    LogisticsManagerProtectedError,
    PasswordTooShortError,
    SuperAdminProtectedError,
    UserNotFoundError,
    UserProfile,
    UserSummary,
    create_managed_user,
    get_user_profile,
    get_user_summary,
    list_users,
    reset_user_password,
    update_user,
)

# Không đặt prefix và không gắn dependency ở mức router: /me mở cho mọi User đăng nhập,
# còn các route quản trị tự khai UserAdminDep.
router = APIRouter(tags=["users"])


class CreateUserRequest(BaseModel):
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    # EmailStr từ chối tên miền dành riêng như .local hay .test.
    email: EmailStr
    role: AssignableRole
    # Không đặt min_length: độ dài do check_password_policy quyết, như ở /auth/password.
    password: str


class UpdateUserRequest(BaseModel):
    role: AssignableRole | None = None
    is_locked: bool | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str


# Mọi lỗi nghiệp vụ của thao tác quản trị đổi sang mã HTTP ở một chỗ.
ADMIN_ERROR_STATUS: dict[type[Exception], int] = {
    PasswordTooShortError: 422,
    EmailTakenError: 409,
    UserNotFoundError: 404,
    SuperAdminProtectedError: 403,
    LogisticsManagerProtectedError: 403,
}
ADMIN_ERRORS = tuple(ADMIN_ERROR_STATUS)


def admin_error(error: Exception) -> HTTPException:
    return HTTPException(status_code=ADMIN_ERROR_STATUS[type(error)], detail=str(error))


# Đọc từ cơ sở dữ liệu chứ không chép lại token, để "tôi là ai" luôn phản ánh hiện trạng
# — token có thể lệch tên, vai trò, claim tối đa 15 phút.
@router.get("/me")
async def me(current_user: CurrentUserDep, session: SessionDep) -> UserProfile:
    return await get_user_profile(session, current_user.user_id)


@router.get("/users")
async def users(_: UserAdminDep, session: SessionDep) -> list[UserSummary]:
    return await list_users(session)


@router.post("/users", status_code=201)
async def create(
    body: CreateUserRequest, admin: UserAdminDep, session: SessionDep
) -> UserSummary:
    try:
        user_id = await create_managed_user(
            session,
            actor_role=admin.role,
            email=body.email,
            password=body.password,
            display_name=body.display_name,
            role=body.role,
        )
    except ADMIN_ERRORS as error:
        raise admin_error(error) from None
    return await get_user_summary(session, user_id)


@router.patch("/users/{user_id}")
async def update(
    user_id: int, body: UpdateUserRequest, admin: UserAdminDep, session: SessionDep
) -> UserSummary:
    try:
        return await update_user(
            session,
            actor_role=admin.role,
            user_id=user_id,
            role=body.role,
            is_locked=body.is_locked,
        )
    except ADMIN_ERRORS as error:
        raise admin_error(error) from None


@router.post("/users/{user_id}/password", status_code=204)
async def reset_password(
    user_id: int, body: ResetPasswordRequest, admin: UserAdminDep, session: SessionDep
) -> None:
    try:
        await reset_user_password(
            session,
            actor_role=admin.role,
            user_id=user_id,
            new_password=body.new_password,
        )
    except ADMIN_ERRORS as error:
        raise admin_error(error) from None
