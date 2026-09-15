from datetime import datetime
from typing import Annotated

import sqlalchemy as sa
from pydantic import BaseModel, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import Role, users
from app.models.derived import orders
from app.models.notes import order_notes

# Cắt khoảng trắng trước rồi mới đếm độ dài: ghi chú chỉ toàn khoảng trắng là rỗng. Cùng
# khoảng với ck_order_notes_body_length của bảng.
NoteBody = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]


class NewOrderNote(BaseModel):
    body: NoteBody


class NoteAuthor(BaseModel):
    display_name: str
    role: Role


class OrderNote(BaseModel):
    id: int
    body: str
    created_at: datetime
    author: NoteAuthor


# Tên và vai trò tác giả đọc bằng JOIN lúc đọc, không chép vào ghi chú. User không bao giờ
# bị xóa, và Locked User vẫn là tác giả, nên JOIN thường không làm rơi ghi chú nào.
_NOTE_COLUMNS = sa.select(
    order_notes.c.id,
    order_notes.c.body,
    order_notes.c.created_at,
    users.c.display_name,
    users.c.role,
).join(users, users.c.id == order_notes.c.author_id)


def _to_note(row: sa.Row) -> OrderNote:
    return OrderNote(
        id=row.id,
        body=row.body,
        created_at=row.created_at,
        author=NoteAuthor(display_name=row.display_name, role=row.role),
    )


async def _order_exists(session: AsyncSession, order_id: str) -> bool:
    found = await session.scalar(sa.select(1).where(orders.c.order_id == order_id))
    return found is not None


async def list_order_notes(session: AsyncSession, order_id: str) -> list[OrderNote] | None:
    """Ghi chú của đơn, mới nhất trên cùng; None nếu không có đơn nào mang mã đó."""
    if not await _order_exists(session, order_id):
        return None
    rows = await session.execute(
        _NOTE_COLUMNS.where(order_notes.c.order_id == order_id)
        # id phá thế hoà khi hai ghi chú trùng thời điểm.
        .order_by(order_notes.c.created_at.desc(), order_notes.c.id.desc())
    )
    return [_to_note(row) for row in rows]


async def add_order_note(
    session: AsyncSession, order_id: str, author_id: int, body: str
) -> OrderNote | None:
    """Thêm một ghi chú; None nếu không có đơn nào mang mã đó.

    Bảng không có khoá ngoại tới orders (xem app/models/notes.py), nên đây là chỗ duy nhất
    chặn ghi chú mồ côi.
    """
    if not await _order_exists(session, order_id):
        return None
    note_id = await session.scalar(
        sa.insert(order_notes)
        .values(order_id=order_id, author_id=author_id, body=body)
        .returning(order_notes.c.id)
    )
    await session.commit()
    row = (await session.execute(_NOTE_COLUMNS.where(order_notes.c.id == note_id))).one()
    return _to_note(row)
