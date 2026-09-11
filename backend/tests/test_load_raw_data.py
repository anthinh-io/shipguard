import csv

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.models.raw import CSV_TO_TABLE
from app.scripts.load_raw_data import CSV_DIR, load_all


def _csv_row_count(filename: str) -> int:
    with open(CSV_DIR / filename, encoding="utf-8-sig", newline="") as f:
        return sum(1 for _ in csv.reader(f)) - 1


async def test_load_all_matches_csv_row_counts_and_is_idempotent() -> None:
    expected_counts = {
        filename: _csv_row_count(filename) for filename in CSV_TO_TABLE
    }

    engine = create_async_engine(settings.TEST_DATABASE_URL)
    try:
        first_run_counts = await load_all(settings.TEST_DATABASE_URL, CSV_DIR)
        assert first_run_counts == expected_counts

        async with engine.connect() as connection:
            for filename, table in CSV_TO_TABLE.items():
                actual = await connection.scalar(select(func.count()).select_from(table))
                assert actual == expected_counts[filename]

        second_run_counts = await load_all(settings.TEST_DATABASE_URL, CSV_DIR)
        assert second_run_counts == expected_counts
    finally:
        await engine.dispose()
