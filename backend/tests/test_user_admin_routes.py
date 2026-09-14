from typing import Any

import jwt
import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import ALGORITHM
from app.models.auth import users
from app.services.users import create_user

PASSWORD = "correct-horse-battery"
NEW_PASSWORD = "staple-battery-horse"

SUPER_ADMIN = "admin@shipguard.vn"
MANAGER = "khoa@shipguard.vn"
OTHER_MANAGER = "minh@shipguard.vn"
STAFF = "lan@shipguard.vn"


# Người thật trong cơ sở dữ liệu, không phải token mượn id: route quản trị tra dòng của
# người bị tác động và so id người gọi, nên id trong token phải khớp một dòng có thật.
@pytest.fixture
async def accounts(auth_session: AsyncSession) -> dict[str, int]:
    people = [
        (SUPER_ADMIN, "Super Admin", "super_admin"),
        (MANAGER, "Trần Khoa", "logistics_manager"),
        (OTHER_MANAGER, "Lê Minh", "logistics_manager"),
        (STAFF, "Nguyễn Lan", "operations_staff"),
    ]
    return {
        email: await create_user(
            auth_session,
            email=email,
            password=PASSWORD,
            display_name=name,
            role=role,
        )
        for email, name, role in people
    }


async def login(client: AsyncClient, email: str, password: str = PASSWORD) -> Response:
    return await client.post("/auth/login", json={"email": email, "password": password})


async def token_for(client: AsyncClient, email: str) -> str:
    response = await login(client, email)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def bearer(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def refresh_cookie(token: str) -> dict[str, str]:
    return {"Cookie": f"refresh_token={token}"}


async def count_users(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(users))


async def act(
    client: AsyncClient,
    actor: str,
    method: str,
    url: str,
    json: dict[str, Any] | None = None,
) -> Response:
    headers = bearer(await token_for(client, actor))
    return await client.request(method, url, headers=headers, json=json)


async def test_listing_users_requires_a_session(
    client: AsyncClient, accounts: dict[str, int]
) -> None:
    response = await client.get("/users")

    assert response.status_code == 401


@pytest.mark.parametrize("actor", [MANAGER, SUPER_ADMIN])
async def test_manager_and_super_admin_see_every_account(
    client: AsyncClient, accounts: dict[str, int], actor: str
) -> None:
    response = await act(client, actor, "GET", "/users")

    assert response.status_code == 200
    body = response.json()
    assert [user["email"] for user in body] == [
        SUPER_ADMIN,
        MANAGER,
        OTHER_MANAGER,
        STAFF,
    ]
    assert body[3] == {
        "id": accounts[STAFF],
        "email": STAFF,
        "display_name": "Nguyễn Lan",
        "role": "operations_staff",
        "is_locked": False,
    }


# Mỗi thao tác đều nhắm vào một người quản lý được, để 403 chỉ có thể đến từ vai trò
# người gọi chứ không phải từ quy tắc bảo vệ Super Admin hay chính mình.
@pytest.mark.parametrize(
    ("method", "path", "json"),
    [
        ("GET", "/users", None),
        (
            "POST",
            "/users",
            {
                "display_name": "Người mới",
                "email": "new@shipguard.vn",
                "role": "operations_staff",
                "password": PASSWORD,
            },
        ),
        ("PATCH", "/users/{target}", {"is_locked": True}),
        ("POST", "/users/{target}/password", {"new_password": NEW_PASSWORD}),
    ],
    ids=["list", "create", "update", "reset password"],
)
async def test_operations_staff_is_refused_every_admin_endpoint(
    client: AsyncClient,
    auth_session: AsyncSession,
    accounts: dict[str, int],
    method: str,
    path: str,
    json: dict[str, Any] | None,
) -> None:
    url = path.format(target=accounts[OTHER_MANAGER])

    response = await act(client, STAFF, method, url, json)

    assert response.status_code == 403
    assert await count_users(auth_session) == 4
    assert (await login(client, OTHER_MANAGER)).status_code == 200


def new_account(**overrides: str) -> dict[str, str]:
    return {
        "display_name": "Phạm Hoa",
        "email": "hoa@shipguard.vn",
        "role": "operations_staff",
        "password": NEW_PASSWORD,
        **overrides,
    }


async def test_created_user_can_sign_in_right_away(
    client: AsyncClient, accounts: dict[str, int]
) -> None:
    response = await act(client, MANAGER, "POST", "/users", new_account())

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "id": body["id"],
        "email": "hoa@shipguard.vn",
        "display_name": "Phạm Hoa",
        "role": "operations_staff",
        "is_locked": False,
    }
    signed_in = await login(client, "hoa@shipguard.vn", NEW_PASSWORD)
    assert signed_in.status_code == 200


async def test_email_already_in_use_in_any_case_is_refused(
    client: AsyncClient, auth_session: AsyncSession, accounts: dict[str, int]
) -> None:
    response = await act(
        client, MANAGER, "POST", "/users", new_account(email="LAN@ShipGuard.VN")
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Email is already in use"}
    assert await count_users(auth_session) == 4


@pytest.mark.parametrize(
    "overrides",
    [
        {"role": "super_admin"},
        {"password": "7-chars"},
        {"display_name": "   "},
        {"email": "not-an-email"},
    ],
    ids=["super admin role", "short password", "blank name", "malformed email"],
)
async def test_create_rejects_invalid_input(
    client: AsyncClient,
    auth_session: AsyncSession,
    accounts: dict[str, int],
    overrides: dict[str, str],
) -> None:
    response = await act(client, MANAGER, "POST", "/users", new_account(**overrides))

    assert response.status_code == 422
    assert await count_users(auth_session) == 4


async def test_super_admin_creates_the_first_logistics_manager(
    client: AsyncClient, auth_session: AsyncSession
) -> None:
    await create_user(
        auth_session,
        email=SUPER_ADMIN,
        password=PASSWORD,
        display_name="Super Admin",
        role="super_admin",
    )

    response = await act(
        client, SUPER_ADMIN, "POST", "/users", new_account(role="logistics_manager")
    )

    assert response.status_code == 201
    signed_in = await login(client, "hoa@shipguard.vn", NEW_PASSWORD)
    listed = await client.get(
        "/users", headers=bearer(signed_in.json()["access_token"])
    )
    assert listed.status_code == 200


async def test_locked_user_cannot_sign_in_and_loses_every_session(
    client: AsyncClient, accounts: dict[str, int]
) -> None:
    old_session = (await login(client, STAFF)).cookies["refresh_token"]

    response = await act(
        client, MANAGER, "PATCH", f"/users/{accounts[STAFF]}", {"is_locked": True}
    )

    assert response.status_code == 200
    assert response.json()["is_locked"] is True
    assert (await login(client, STAFF)).status_code == 401
    refreshed = await client.post("/auth/refresh", headers=refresh_cookie(old_session))
    assert refreshed.status_code == 401


async def test_unlocked_user_can_sign_in_again(
    client: AsyncClient, accounts: dict[str, int]
) -> None:
    url = f"/users/{accounts[STAFF]}"
    await act(client, MANAGER, "PATCH", url, {"is_locked": True})

    response = await act(client, MANAGER, "PATCH", url, {"is_locked": False})

    assert response.status_code == 200
    assert response.json()["is_locked"] is False
    assert (await login(client, STAFF)).status_code == 200


async def test_role_change_ends_sessions_and_next_login_carries_the_new_role(
    client: AsyncClient, accounts: dict[str, int]
) -> None:
    old_session = (await login(client, STAFF)).cookies["refresh_token"]

    response = await act(
        client,
        MANAGER,
        "PATCH",
        f"/users/{accounts[STAFF]}",
        {"role": "logistics_manager"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "logistics_manager"
    refreshed = await client.post("/auth/refresh", headers=refresh_cookie(old_session))
    assert refreshed.status_code == 401
    token = await token_for(client, STAFF)
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["role"] == "logistics_manager"
    me = await client.get("/me", headers=bearer(token))
    assert me.json()["role"] == "logistics_manager"


async def test_role_cannot_be_changed_to_super_admin(
    client: AsyncClient, accounts: dict[str, int]
) -> None:
    response = await act(
        client, MANAGER, "PATCH", f"/users/{accounts[STAFF]}", {"role": "super_admin"}
    )

    assert response.status_code == 422
    assert (await login(client, STAFF)).status_code == 200


async def test_password_reset_works_and_signs_out_old_sessions(
    client: AsyncClient, accounts: dict[str, int]
) -> None:
    old_session = (await login(client, STAFF)).cookies["refresh_token"]

    response = await act(
        client,
        MANAGER,
        "POST",
        f"/users/{accounts[STAFF]}/password",
        {"new_password": NEW_PASSWORD},
    )

    assert response.status_code == 204
    assert (await login(client, STAFF, NEW_PASSWORD)).status_code == 200
    assert (await login(client, STAFF)).status_code == 401
    refreshed = await client.post("/auth/refresh", headers=refresh_cookie(old_session))
    assert refreshed.status_code == 401


async def test_password_reset_rejects_a_short_password(
    client: AsyncClient, accounts: dict[str, int]
) -> None:
    old_session = (await login(client, STAFF)).cookies["refresh_token"]

    response = await act(
        client,
        MANAGER,
        "POST",
        f"/users/{accounts[STAFF]}/password",
        {"new_password": "short"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Password must be at least 8 characters"}
    assert (await login(client, STAFF)).status_code == 200
    refreshed = await client.post("/auth/refresh", headers=refresh_cookie(old_session))
    assert refreshed.status_code == 200


ADMIN_ACTIONS = [
    ("PATCH", "/users/{target}", {"is_locked": True}),
    ("PATCH", "/users/{target}", {"role": "operations_staff"}),
    ("POST", "/users/{target}/password", {"new_password": NEW_PASSWORD}),
]
ADMIN_ACTION_IDS = ["lock", "change role", "reset password"]


@pytest.mark.parametrize("actor", [MANAGER, SUPER_ADMIN])
@pytest.mark.parametrize(
    ("method", "path", "json"), ADMIN_ACTIONS, ids=ADMIN_ACTION_IDS
)
async def test_no_admin_action_touches_the_super_admin(
    client: AsyncClient,
    accounts: dict[str, int],
    actor: str,
    method: str,
    path: str,
    json: dict[str, Any],
) -> None:
    url = path.format(target=accounts[SUPER_ADMIN])

    response = await act(client, actor, method, url, json)

    assert response.status_code == 403
    assert response.json() == {"detail": "The Super Admin cannot be managed"}
    super_admin = (await login(client, SUPER_ADMIN)).json()["access_token"]
    me = await client.get("/me", headers=bearer(super_admin))
    assert me.json()["role"] == "super_admin"


@pytest.mark.parametrize(
    ("method", "path", "json"), ADMIN_ACTIONS, ids=ADMIN_ACTION_IDS
)
async def test_no_admin_action_on_yourself(
    client: AsyncClient,
    accounts: dict[str, int],
    method: str,
    path: str,
    json: dict[str, Any],
) -> None:
    url = path.format(target=accounts[MANAGER])

    response = await act(client, MANAGER, method, url, json)

    assert response.status_code == 403
    assert response.json() == {"detail": "You cannot manage your own account here"}
    token = await token_for(client, MANAGER)
    me = await client.get("/me", headers=bearer(token))
    assert me.json()["role"] == "logistics_manager"


async def test_manager_can_manage_another_manager(
    client: AsyncClient, accounts: dict[str, int]
) -> None:
    response = await act(
        client,
        MANAGER,
        "PATCH",
        f"/users/{accounts[OTHER_MANAGER]}",
        {"is_locked": True},
    )

    assert response.status_code == 200
    assert (await login(client, OTHER_MANAGER)).status_code == 401


@pytest.mark.parametrize(
    ("method", "path", "json"), ADMIN_ACTIONS, ids=ADMIN_ACTION_IDS
)
async def test_unknown_user_is_not_found(
    client: AsyncClient,
    accounts: dict[str, int],
    method: str,
    path: str,
    json: dict[str, Any],
) -> None:
    response = await act(client, MANAGER, method, path.format(target=999_999), json)

    assert response.status_code == 404


async def test_users_cannot_be_deleted(
    client: AsyncClient, auth_session: AsyncSession, accounts: dict[str, int]
) -> None:
    response = await act(client, MANAGER, "DELETE", f"/users/{accounts[STAFF]}")

    assert response.status_code == 405
    assert await count_users(auth_session) == 4
