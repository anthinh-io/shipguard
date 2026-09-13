from pydantic import BaseModel
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.auth import Role, users
from app.services.auth import load_claims, normalize_email, revoke_all_refresh_tokens

MIN_PASSWORD_LENGTH = 8


class PasswordTooShortError(ValueError):
    def __init__(self) -> None:
        super().__init__(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")


class SuperAdminEmailTakenError(RuntimeError):
    def __init__(self, email: str) -> None:
        super().__init__(
            f"SUPER_ADMIN_EMAIL {email} already belongs to a User who is not the "
            "Super Admin. Set SUPER_ADMIN_EMAIL to an unused address and start again."
        )


class SuperAdminMissingError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "No Super Admin exists yet. Start the backend once to create it from "
            "SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD and SUPER_ADMIN_NAME."
        )


class UserProfile(BaseModel):
    id: int
    email: str
    display_name: str
    role: Role
    claims: list[str]


def check_password_policy(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordTooShortError


# User không bao giờ bị xóa (CONTEXT.md), nên một user_id lấy từ token đã ký luôn có dòng.
async def get_user_profile(session: AsyncSession, user_id: int) -> UserProfile:
    user = (await session.execute(select(users).where(users.c.id == user_id))).one()
    return UserProfile(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        claims=await load_claims(session, user_id),
    )


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: str,
    role: Role,
    is_locked: bool = False,
) -> int:
    check_password_policy(password)
    user_id = await session.scalar(
        insert(users)
        .values(
            email=normalize_email(email),
            display_name=display_name,
            password_hash=await hash_password(password),
            role=role,
            is_locked=is_locked,
        )
        .returning(users.c.id)
    )
    await session.commit()
    return user_id


async def _super_admin_id(session: AsyncSession) -> int | None:
    return await session.scalar(select(users.c.id).where(users.c.role == "super_admin"))


async def ensure_super_admin(
    session: AsyncSession, *, email: str, password: str, display_name: str
) -> bool:
    """Tạo Super Admin nếu chưa có; trả True khi vừa tạo.

    Đã có thì không đọc cấu hình, không đổi gì — cấu hình chỉ dùng cho lần cài đặt đầu.
    """
    if await _super_admin_id(session) is not None:
        return False
    normalized = normalize_email(email)
    taken = await session.scalar(select(users.c.id).where(users.c.email == normalized))
    if taken is not None:
        raise SuperAdminEmailTakenError(normalized)
    await create_user(
        session,
        email=normalized,
        password=password,
        display_name=display_name,
        role="super_admin",
    )
    return True


async def reset_super_admin_password(session: AsyncSession, new_password: str) -> None:
    check_password_policy(new_password)
    user_id = await _super_admin_id(session)
    if user_id is None:
        raise SuperAdminMissingError
    # Đổi mật khẩu và thu hồi phiên trong cùng một transaction: không có khoảnh khắc nào
    # mật khẩu đã đổi mà phiên cũ vẫn làm mới được.
    await session.execute(
        update(users)
        .where(users.c.id == user_id)
        .values(password_hash=await hash_password(new_password))
    )
    await revoke_all_refresh_tokens(session, user_id)
    await session.commit()
