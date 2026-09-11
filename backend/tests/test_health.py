from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

import pytest
from httpx import AsyncClient
from sqlalchemy.engine import URL, make_url

from app.core.config import settings

REFUSED_PORT = make_url(settings.TEST_DATABASE_URL).set(port=1)
WRONG_PASSWORD = make_url(settings.TEST_DATABASE_URL).set(password="wrong-password")

ClientForDatabase = Callable[[str | URL], AbstractAsyncContextManager[AsyncClient]]


async def test_health_reports_database_connected(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


@pytest.mark.parametrize(
    "broken_url",
    [REFUSED_PORT, WRONG_PASSWORD],
    ids=["connection refused", "wrong credentials"],
)
async def test_health_reports_503_when_database_unusable(
    broken_url: URL, client_for_database: ClientForDatabase
) -> None:
    async with client_for_database(broken_url) as client:
        response = await client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "disconnected"}
