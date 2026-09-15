import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.core.config import settings
from app.main import app
from app.scripts.build_derived_data import build_all
from app.scripts.load_raw_data import CSV_DIR, load_all

BACKEND_ROOT = Path(__file__).resolve().parents[1]


async def create_database_if_missing(url: str) -> None:
    target = make_url(url)
    admin_engine = create_async_engine(
        target.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    async with admin_engine.connect() as connection:
        exists = await connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": target.database},
        )
        if not exists:
            await connection.execute(text(f'CREATE DATABASE "{target.database}"'))
    await admin_engine.dispose()


@asynccontextmanager
async def _client_using_database(url: str | URL) -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as async_client:
            yield async_client
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


def _target(url: str) -> tuple[str | None, int | None, str | None]:
    parsed = make_url(url)
    return parsed.host, parsed.port, parsed.database


@pytest.fixture(scope="session", autouse=True)
def test_database() -> None:
    assert _target(settings.TEST_DATABASE_URL) != _target(settings.DATABASE_URL), (
        "TEST_DATABASE_URL must point at a different database from DATABASE_URL: "
        "this fixture migrates it, and pointing both at the same database would "
        "run migrations over development data"
    )
    asyncio.run(create_database_if_missing(settings.TEST_DATABASE_URL))
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.attributes["db_url"] = settings.TEST_DATABASE_URL
    command.upgrade(config, "head")


# Nạp thô và dựng bảng dẫn xuất một lần cho cả phiên. Khai báo phụ thuộc qua tham số
# là ràng buộc cứng trong đồ thị fixture, nên thứ tự luôn là migration -> nạp thô ->
# dựng dẫn xuất, không phụ thuộc vào thứ tự chạy của các test.
@pytest.fixture(scope="session")
def raw_data(test_database: None) -> dict[str, int]:
    return asyncio.run(load_all(settings.TEST_DATABASE_URL, CSV_DIR))


@pytest.fixture(scope="session")
def derived_data(raw_data: dict[str, int]) -> dict[str, int]:
    return asyncio.run(build_all(settings.TEST_DATABASE_URL))


# Phụ thuộc derived_data là bắt buộc, không phải trang trí: engine trần không kéo theo
# bước nạp dữ liệu, nên thiếu nó thì một tệp test chạy riêng sẽ đọc phải bảng rỗng.
@pytest.fixture
async def session(derived_data: dict[str, int]) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(settings.TEST_DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
            yield db
    finally:
        await engine.dispose()


# Chỉ phụ thuộc migration, không kéo bước nạp dữ liệu: test đăng nhập không đọc đơn hàng.
# Dọn sạch mỗi test vì chỉ mục "đúng một super_admin" làm test phụ thuộc thứ tự nếu một
# test để lại Super Admin cho test sau. order_notes phải xoá cùng lượt: ghi chú có khoá
# ngoại tới tác giả, nên TRUNCATE users một mình bị từ chối.
@pytest.fixture
async def auth_session(test_database: None) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(settings.TEST_DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
            await db.execute(
                text(
                    "TRUNCATE order_notes, user_claims, refresh_tokens, users "
                    "RESTART IDENTITY"
                )
            )
            await db.commit()
            yield db
    finally:
        await engine.dispose()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with _client_using_database(settings.TEST_DATABASE_URL) as async_client:
        yield async_client


@pytest.fixture
def client_for_database() -> (
    Callable[[str | URL], AbstractAsyncContextManager[AsyncClient]]
):
    return _client_using_database
