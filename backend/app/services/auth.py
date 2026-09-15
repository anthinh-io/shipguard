from datetime import UTC, datetime

from sqlalchemy import Row, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    REFRESH_TOKEN_TTL,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.models.auth import refresh_tokens, user_claims, users


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def authenticate(session: AsyncSession, email: str, password: str) -> Row | None:
    """None cho mọi kiểu thất bại — không có email, sai mật khẩu, bị khóa — để route
    không thể vô tình trả thông báo khác nhau cho từng trường hợp."""
    user = (
        await session.execute(
            select(users).where(users.c.email == normalize_email(email))
        )
    ).one_or_none()
    if user is None or user.is_locked:
        return None
    if not await verify_password(password, user.password_hash):
        return None
    return user


# Sắp theo tên để cùng một tập claim luôn cho ra cùng một token.
async def load_claims(session: AsyncSession, user_id: int) -> list[str]:
    result = await session.scalars(
        select(user_claims.c.claim)
        .where(user_claims.c.user_id == user_id)
        .order_by(user_claims.c.claim)
    )
    return list(result)


async def issue_refresh_token(session: AsyncSession, user_id: int) -> str:
    raw = new_refresh_token()
    await session.execute(
        insert(refresh_tokens).values(
            user_id=user_id,
            token_hash=hash_refresh_token(raw),
            expires_at=datetime.now(UTC) + REFRESH_TOKEN_TTL,
        )
    )
    await session.commit()
    return raw


async def rotate_refresh_token(
    session: AsyncSession, raw: str
) -> tuple[Row, str] | None:
    # Thu hồi và kiểm tra trong cùng một câu: hai lần làm mới đồng thời bằng cùng một
    # token thì chỉ một lần thấy dòng còn hiệu lực, lần kia nhận None.
    user_id = await session.scalar(
        update(refresh_tokens)
        .where(
            refresh_tokens.c.token_hash == hash_refresh_token(raw),
            refresh_tokens.c.revoked_at.is_(None),
            refresh_tokens.c.expires_at > func.now(),
        )
        .values(revoked_at=func.now())
        .returning(refresh_tokens.c.user_id)
    )
    if user_id is None:
        await session.rollback()
        return None
    user = (await session.execute(select(users).where(users.c.id == user_id))).one()
    if user.is_locked:
        # Vẫn commit: token vừa dùng phải ở trạng thái đã thu hồi.
        await session.commit()
        return None
    return user, await issue_refresh_token(session, user_id)


async def revoke_refresh_token(session: AsyncSession, raw: str) -> None:
    await session.execute(
        update(refresh_tokens)
        .where(
            refresh_tokens.c.token_hash == hash_refresh_token(raw),
            refresh_tokens.c.revoked_at.is_(None),
        )
        .values(revoked_at=func.now())
    )
    await session.commit()


async def revoke_all_refresh_tokens(session: AsyncSession, user_id: int) -> None:
    """Không commit: người gọi gộp việc này vào cùng transaction với thay đổi đã gây ra
    nó, như đặt lại mật khẩu."""
    await session.execute(
        update(refresh_tokens)
        .where(
            refresh_tokens.c.user_id == user_id,
            refresh_tokens.c.revoked_at.is_(None),
        )
        .values(revoked_at=func.now())
    )
