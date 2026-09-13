from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient, Response
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import ALGORITHM
from app.models.auth import refresh_tokens, user_claims, users
from app.services.users import create_user

PASSWORD = "correct-horse-battery"


@pytest.fixture
async def staff_id(auth_session: AsyncSession) -> int:
    return await create_user(
        auth_session,
        email="lan@shipguard.vn",
        password=PASSWORD,
        display_name="Nguyễn Lan",
        role="operations_staff",
    )


async def login(client: AsyncClient, email: str = "lan@shipguard.vn") -> Response:
    return await client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    )


def decode(access_token: str) -> dict:
    return jwt.decode(access_token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM])


def bearer(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


# Gửi cookie tường minh thay vì dựa vào cookie jar của client: test cần gửi lại đúng một
# token cũ sau khi jar đã bị ghi đè bằng token mới.
def refresh_cookie(token: str) -> dict[str, str]:
    return {"Cookie": f"refresh_token={token}"}


async def test_login_then_me_knows_name_and_role(
    client: AsyncClient, staff_id: int
) -> None:
    response = await login(client)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    me = await client.get("/me", headers=bearer(body["access_token"]))
    assert me.status_code == 200
    assert me.json() == {
        "id": staff_id,
        "email": "lan@shipguard.vn",
        "display_name": "Nguyễn Lan",
        "role": "operations_staff",
        "claims": [],
    }


async def test_login_ignores_email_case(client: AsyncClient, staff_id: int) -> None:
    response = await login(client, email="  LAN@ShipGuard.VN ")

    assert response.status_code == 200


async def test_access_token_carries_role_and_claims(
    client: AsyncClient, auth_session: AsyncSession, staff_id: int
) -> None:
    await auth_session.execute(
        insert(user_claims),
        [
            {"user_id": staff_id, "claim": "orders:export"},
            {"user_id": staff_id, "claim": "notes:pin"},
        ],
    )
    await auth_session.commit()

    access_token = (await login(client)).json()["access_token"]

    payload = decode(access_token)
    assert payload["sub"] == str(staff_id)
    assert payload["role"] == "operations_staff"
    assert payload["claims"] == ["notes:pin", "orders:export"]
    me = await client.get("/me", headers=bearer(access_token))
    assert me.json()["claims"] == ["notes:pin", "orders:export"]


async def test_claim_granted_after_login_arrives_with_next_refresh(
    client: AsyncClient, auth_session: AsyncSession, staff_id: int
) -> None:
    response = await login(client)
    assert decode(response.json()["access_token"])["claims"] == []

    await auth_session.execute(
        insert(user_claims).values(user_id=staff_id, claim="orders:export")
    )
    await auth_session.commit()
    refreshed = await client.post(
        "/auth/refresh", headers=refresh_cookie(response.cookies["refresh_token"])
    )

    assert refreshed.status_code == 200
    assert decode(refreshed.json()["access_token"])["claims"] == ["orders:export"]


@pytest.fixture
async def locked_user(auth_session: AsyncSession) -> None:
    await create_user(
        auth_session,
        email="khoa@shipguard.vn",
        password=PASSWORD,
        display_name="Trần Khoa",
        role="logistics_manager",
        is_locked=True,
    )


@pytest.mark.parametrize(
    "credentials",
    [
        {"email": "lan@shipguard.vn", "password": "wrong-password"},
        {"email": "nobody@shipguard.vn", "password": PASSWORD},
        {"email": "khoa@shipguard.vn", "password": PASSWORD},
        {"email": "lan@shipguard.vn", "password": "abc"},
    ],
    ids=["wrong password", "unknown email", "locked user", "too short to be valid"],
)
@pytest.mark.usefixtures("staff_id", "locked_user")
async def test_failed_logins_look_identical(
    client: AsyncClient, credentials: dict[str, str]
) -> None:
    response = await client.post("/auth/login", json=credentials)

    # Cùng mã, cùng thân: người ngoài không phân biệt được email nào tồn tại hay bị khóa.
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}
    assert "refresh_token" not in response.cookies


async def test_refresh_cookie_is_http_only_and_scoped_to_auth(
    client: AsyncClient, auth_session: AsyncSession, staff_id: int
) -> None:
    response = await login(client)

    set_cookie = response.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Path=/auth" in set_cookie
    assert f"Max-Age={7 * 24 * 60 * 60}" in set_cookie
    # Chỉ bản băm được lưu, chuỗi thô trong cookie không có trong cơ sở dữ liệu.
    raw = response.cookies["refresh_token"]
    stored = (await auth_session.scalars(select(refresh_tokens.c.token_hash))).all()
    assert len(stored) == 1
    assert raw not in stored


async def test_refresh_rotates_and_the_old_token_is_single_use(
    client: AsyncClient, staff_id: int
) -> None:
    old_token = (await login(client)).cookies["refresh_token"]

    refreshed = await client.post("/auth/refresh", headers=refresh_cookie(old_token))

    assert refreshed.status_code == 200
    new_token = refreshed.cookies["refresh_token"]
    assert new_token != old_token
    me = await client.get("/me", headers=bearer(refreshed.json()["access_token"]))
    assert me.status_code == 200

    reused = await client.post("/auth/refresh", headers=refresh_cookie(old_token))
    assert reused.status_code == 401
    assert reused.json() == {"detail": "Invalid refresh token"}

    # Token mới vẫn dùng được: dùng lại token cũ không kéo token mới đổ theo.
    again = await client.post("/auth/refresh", headers=refresh_cookie(new_token))
    assert again.status_code == 200


async def test_refresh_rejects_missing_or_expired_token(
    client: AsyncClient, auth_session: AsyncSession, staff_id: int
) -> None:
    token = (await login(client)).cookies["refresh_token"]
    await auth_session.execute(
        update(refresh_tokens).values(
            expires_at=datetime.now(UTC) - timedelta(seconds=1)
        )
    )
    await auth_session.commit()

    expired = await client.post("/auth/refresh", headers=refresh_cookie(token))
    client.cookies.clear()
    missing = await client.post("/auth/refresh")

    assert expired.status_code == 401
    assert missing.status_code == 401


async def test_refresh_rejects_a_locked_user(
    client: AsyncClient, auth_session: AsyncSession, staff_id: int
) -> None:
    token = (await login(client)).cookies["refresh_token"]
    await auth_session.execute(update(users).values(is_locked=True))
    await auth_session.commit()

    response = await client.post("/auth/refresh", headers=refresh_cookie(token))

    assert response.status_code == 401


async def test_logout_ends_the_session(client: AsyncClient, staff_id: int) -> None:
    token = (await login(client)).cookies["refresh_token"]

    response = await client.post("/auth/logout", headers=refresh_cookie(token))

    assert response.status_code == 204
    set_cookie = response.headers["set-cookie"]
    assert "refresh_token=" in set_cookie
    assert "Max-Age=0" in set_cookie
    # Xóa phải cùng Path với lúc đặt, nếu không trình duyệt giữ nguyên cookie cũ.
    assert "Path=/auth" in set_cookie
    after = await client.post("/auth/refresh", headers=refresh_cookie(token))
    assert after.status_code == 401


async def test_logout_without_a_session_still_succeeds(
    client: AsyncClient, auth_session: AsyncSession
) -> None:
    response = await client.post("/auth/logout")

    assert response.status_code == 204


OTHER_SECRET = "some-other-secret-key-long-enough-for-hs256"


def forged_token(user_id: int, secret: str, expires_in: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": "operations_staff",
        "claims": [],
        "iat": now,
        "exp": now + expires_in,
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


# Token hỏng đều trỏ vào một người dùng có thật: nếu bước xác minh bị bỏ qua thì /me sẽ
# tìm thấy người đó và trả 200, nên test không xanh nhờ "không có dòng nào".
@pytest.mark.parametrize(
    "authorization",
    [
        lambda _: None,
        lambda _: "Basic bGFuOnBhc3N3b3Jk",
        lambda uid: "Bearer "
        + forged_token(uid, settings.JWT_SECRET_KEY, timedelta(seconds=-1)),
        lambda uid: "Bearer " + forged_token(uid, OTHER_SECRET, timedelta(minutes=5)),
        lambda _: "Bearer not-a-jwt",
    ],
    ids=["no header", "basic scheme", "expired", "wrong signature", "garbage"],
)
async def test_me_requires_a_valid_session(
    client: AsyncClient, staff_id: int, authorization: Callable[[int], str | None]
) -> None:
    value = authorization(staff_id)
    headers = {} if value is None else {"Authorization": value}

    response = await client.get("/me", headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_cors_preflight_allows_credentialed_auth_calls(
    client: AsyncClient,
) -> None:
    origin = settings.CORS_ALLOWED_ORIGINS[0]

    response = await client.options(
        "/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"
    allowed = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed
    assert "content-type" in allowed
