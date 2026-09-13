import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.auth import user_claims, users
from app.services.auth import authenticate, issue_refresh_token, rotate_refresh_token
from app.services.users import (
    PasswordTooShortError,
    SuperAdminEmailTakenError,
    SuperAdminMissingError,
    create_user,
    ensure_super_admin,
    reset_super_admin_password,
)

CONFIG = {
    "email": "Admin@ShipGuard.local",
    "password": "installer-password",
    "display_name": "Super Admin",
}


async def count_users(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(users))


async def test_fresh_install_creates_a_super_admin_who_can_log_in(
    auth_session: AsyncSession,
) -> None:
    created = await ensure_super_admin(auth_session, **CONFIG)

    assert created is True
    user = await authenticate(auth_session, CONFIG["email"], CONFIG["password"])
    assert user is not None
    assert user.role == "super_admin"
    assert user.email == "admin@shipguard.local"
    # Không bao giờ lưu dạng đọc được.
    assert user.password_hash != CONFIG["password"]
    assert user.password_hash.startswith("$argon2")


async def test_restart_with_different_config_changes_nothing(
    auth_session: AsyncSession,
) -> None:
    await ensure_super_admin(auth_session, **CONFIG)
    before = (await auth_session.execute(select(users))).one()

    created = await ensure_super_admin(
        auth_session,
        email="someone-else@shipguard.local",
        password="another-password",
        display_name="Another Name",
    )

    assert created is False
    assert await count_users(auth_session) == 1
    after = (await auth_session.execute(select(users))).one()
    assert after == before


async def test_config_email_taken_by_a_regular_user_stops_startup(
    auth_session: AsyncSession,
) -> None:
    await create_user(
        auth_session,
        email="admin@shipguard.local",
        password="staff-password",
        display_name="Nhân viên",
        role="operations_staff",
    )

    with pytest.raises(SuperAdminEmailTakenError, match="admin@shipguard.local"):
        await ensure_super_admin(auth_session, **CONFIG)

    assert await count_users(auth_session) == 1


async def test_short_config_password_is_rejected(auth_session: AsyncSession) -> None:
    with pytest.raises(PasswordTooShortError):
        await ensure_super_admin(auth_session, **{**CONFIG, "password": "7-chars"})

    assert await count_users(auth_session) == 0


async def test_database_allows_only_one_super_admin(
    auth_session: AsyncSession,
) -> None:
    await ensure_super_admin(auth_session, **CONFIG)

    with pytest.raises(IntegrityError):
        await auth_session.execute(
            insert(users).values(
                email="second@shipguard.local",
                display_name="Second",
                password_hash=hash_password("whatever-password"),
                role="super_admin",
            )
        )


async def test_database_rejects_emails_differing_only_in_case(
    auth_session: AsyncSession,
) -> None:
    await ensure_super_admin(auth_session, **CONFIG)

    with pytest.raises(IntegrityError):
        await auth_session.execute(
            insert(users).values(
                email="ADMIN@SHIPGUARD.LOCAL",
                display_name="Copy",
                password_hash=hash_password("whatever-password"),
                role="operations_staff",
            )
        )


async def test_database_rejects_a_duplicate_claim(auth_session: AsyncSession) -> None:
    await ensure_super_admin(auth_session, **CONFIG)
    user_id = await auth_session.scalar(select(users.c.id))
    await auth_session.execute(
        insert(user_claims).values(user_id=user_id, claim="orders:export")
    )

    with pytest.raises(IntegrityError):
        await auth_session.execute(
            insert(user_claims).values(user_id=user_id, claim="orders:export")
        )


async def test_password_reset_signs_out_every_old_session(
    auth_session: AsyncSession,
) -> None:
    await ensure_super_admin(auth_session, **CONFIG)
    user_id = await auth_session.scalar(select(users.c.id))
    old_sessions = [await issue_refresh_token(auth_session, user_id) for _ in range(2)]

    await reset_super_admin_password(auth_session, "brand-new-password")

    assert await authenticate(auth_session, CONFIG["email"], "brand-new-password")
    assert await authenticate(auth_session, CONFIG["email"], CONFIG["password"]) is None
    for raw in old_sessions:
        assert await rotate_refresh_token(auth_session, raw) is None


async def test_password_reset_rejects_a_short_password(
    auth_session: AsyncSession,
) -> None:
    await ensure_super_admin(auth_session, **CONFIG)
    user_id = await auth_session.scalar(select(users.c.id))
    session_token = await issue_refresh_token(auth_session, user_id)

    with pytest.raises(PasswordTooShortError):
        await reset_super_admin_password(auth_session, "short")

    assert await authenticate(auth_session, CONFIG["email"], CONFIG["password"])
    assert await rotate_refresh_token(auth_session, session_token) is not None


async def test_password_reset_without_a_super_admin_fails_clearly(
    auth_session: AsyncSession,
) -> None:
    with pytest.raises(SuperAdminMissingError):
        await reset_super_admin_password(auth_session, "brand-new-password")
