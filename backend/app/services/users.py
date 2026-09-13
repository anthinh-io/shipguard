from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.auth import Role, users
from app.services.auth import normalize_email

MIN_PASSWORD_LENGTH = 8


class PasswordTooShortError(ValueError):
    def __init__(self) -> None:
        super().__init__(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")


def check_password_policy(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordTooShortError


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
            password_hash=hash_password(password),
            role=role,
            is_locked=is_locked,
        )
        .returning(users.c.id)
    )
    await session.commit()
    return user_id
