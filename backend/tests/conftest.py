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


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with _client_using_database(settings.TEST_DATABASE_URL) as async_client:
        yield async_client


@pytest.fixture
def client_for_database() -> (
    Callable[[str | URL], AbstractAsyncContextManager[AsyncClient]]
):
    return _client_using_database
