from datetime import datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import rebuild_derived_data

from app.core.config import settings
from app.models.notes import order_notes
from app.services.users import create_user, update_user

pytestmark = pytest.mark.usefixtures("derived_data")

PASSWORD = "correct-horse-battery"
STAFF = "lan@shipguard.vn"
MANAGER = "khoa@shipguard.vn"

ORDER_ID = "e481f51cbdc54678b7cc49136f2d6af7"
OTHER_ORDER_ID = "53cdb2fc8bc7dce0b6741e2150273451"
MISSING_ORDER_ID = "00000000000000000000000000000000"


# Người thật trong cơ sở dữ liệu, không phải token mượn id: ghi chú có khoá ngoại tới tác
# giả và đọc tên tác giả bằng JOIN, nên id trong token phải khớp một dòng có thật.
@pytest.fixture
async def accounts(auth_session: AsyncSession) -> dict[str, int]:
    people = [
        (STAFF, "Nguyễn Lan", "operations_staff"),
        (MANAGER, "Trần Khoa", "logistics_manager"),
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


async def bearer(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def add_note(
    client: AsyncClient, email: str, body: str, order_id: str = ORDER_ID
) -> dict[str, Any]:
    response = await client.post(
        f"/orders/{order_id}/notes",
        json={"body": body},
        headers=await bearer(client, email),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def count_notes(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(order_notes))


async def test_added_note_is_trimmed_and_carries_its_author(
    client: AsyncClient, accounts: dict[str, int]
) -> None:
    body = await add_note(client, STAFF, "  Đã gọi khách, hẹn giao lại thứ Hai.\n ")

    assert body == {
        "id": body["id"],
        "body": "Đã gọi khách, hẹn giao lại thứ Hai.",
        "created_at": body["created_at"],
        "author": {"display_name": "Nguyễn Lan", "role": "operations_staff"},
    }
    # Mốc thật có múi giờ, khác dấu thời gian không múi giờ của dữ liệu Olist.
    assert datetime.fromisoformat(body["created_at"]).tzinfo is not None


async def test_notes_from_several_authors_are_listed_newest_first(
    client: AsyncClient, accounts: dict[str, int]
) -> None:
    first = await add_note(client, STAFF, "Ghi chú thứ nhất")
    second = await add_note(client, MANAGER, "Ghi chú thứ hai")
    third = await add_note(client, STAFF, "Ghi chú thứ ba")
    await add_note(client, MANAGER, "Ghi chú của đơn khác", order_id=OTHER_ORDER_ID)

    response = await client.get(
        f"/orders/{ORDER_ID}/notes", headers=await bearer(client, MANAGER)
    )

    assert response.status_code == 200
    assert response.json() == [third, second, first]
    assert [note["author"]["display_name"] for note in response.json()] == [
        "Nguyễn Lan",
        "Trần Khoa",
        "Nguyễn Lan",
    ]


async def test_order_without_notes_lists_nothing(
    client: AsyncClient, accounts: dict[str, int]
) -> None:
    response = await client.get(
        f"/orders/{ORDER_ID}/notes", headers=await bearer(client, STAFF)
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "body",
    ["", " \n\t ", "a" * 2001],
    ids=["empty", "only whitespace", "2001 characters"],
)
async def test_blank_or_too_long_note_is_refused_and_not_stored(
    client: AsyncClient,
    auth_session: AsyncSession,
    accounts: dict[str, int],
    body: str,
) -> None:
    response = await client.post(
        f"/orders/{ORDER_ID}/notes",
        json={"body": body},
        headers=await bearer(client, STAFF),
    )

    assert response.status_code == 422
    assert await count_notes(auth_session) == 0


async def test_note_of_exactly_2000_characters_after_trimming_is_accepted(
    client: AsyncClient, accounts: dict[str, int]
) -> None:
    body = await add_note(client, STAFF, f"  {'a' * 2000}  ")

    assert body["body"] == "a" * 2000


@pytest.mark.parametrize("method", ["GET", "POST"])
async def test_unknown_order_is_404_and_leaves_no_orphan_note(
    client: AsyncClient,
    auth_session: AsyncSession,
    accounts: dict[str, int],
    method: str,
) -> None:
    response = await client.request(
        method,
        f"/orders/{MISSING_ORDER_ID}/notes",
        json={"body": "Ghi chú lạc"} if method == "POST" else None,
        headers=await bearer(client, STAFF),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Order not found"}
    assert await count_notes(auth_session) == 0


async def test_note_of_a_locked_author_still_shows_their_name_and_role(
    client: AsyncClient, auth_session: AsyncSession, accounts: dict[str, int]
) -> None:
    await add_note(client, STAFF, "Viết trước khi bị khóa")
    await update_user(
        auth_session,
        actor_role="logistics_manager",
        user_id=accounts[STAFF],
        is_locked=True,
    )

    response = await client.get(
        f"/orders/{ORDER_ID}/notes", headers=await bearer(client, MANAGER)
    )

    assert response.status_code == 200
    assert [note["author"] for note in response.json()] == [
        {"display_name": "Nguyễn Lan", "role": "operations_staff"}
    ]


# Mang token hợp lệ để 405 chỉ có thể đến từ việc không có route sửa hay xóa, không lẫn
# với 401 của bài chưa đăng nhập.
@pytest.mark.parametrize("method", ["PATCH", "DELETE"])
async def test_notes_cannot_be_edited_or_deleted(
    client: AsyncClient, accounts: dict[str, int], method: str
) -> None:
    note = await add_note(client, STAFF, "Không sửa được")
    headers = await bearer(client, STAFF)

    response = await client.request(
        method, f"/orders/{ORDER_ID}/notes", json={"body": "Đã sửa"}, headers=headers
    )

    assert response.status_code == 405
    listed = await client.get(f"/orders/{ORDER_ID}/notes", headers=headers)
    assert listed.json() == [note]


@pytest.mark.parametrize("method", ["GET", "POST"])
async def test_notes_require_a_session(
    client: AsyncClient,
    auth_session: AsyncSession,
    accounts: dict[str, int],
    method: str,
) -> None:
    response = await client.request(
        method,
        f"/orders/{ORDER_ID}/notes",
        json={"body": "Không có token"} if method == "POST" else None,
    )

    assert response.status_code == 401
    assert await count_notes(auth_session) == 0


# Hợp đồng với build_derived_data: dựng lại bảng orders từ đầu không được làm mất hay đổi
# bất kỳ ghi chú nào — lý do order_notes không có khoá ngoại tới orders.
async def test_rebuilding_derived_data_keeps_every_note_unchanged(
    client: AsyncClient, accounts: dict[str, int]
) -> None:
    await add_note(client, STAFF, "Trước khi dựng lại")
    await add_note(client, MANAGER, "Cũng trước khi dựng lại")
    headers = await bearer(client, STAFF)
    before = (await client.get(f"/orders/{ORDER_ID}/notes", headers=headers)).json()

    await rebuild_derived_data(settings.TEST_DATABASE_URL)

    after = await client.get(f"/orders/{ORDER_ID}/notes", headers=headers)
    assert after.status_code == 200
    assert len(before) == 2
    assert after.json() == before
