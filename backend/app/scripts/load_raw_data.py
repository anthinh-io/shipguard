import asyncio
from pathlib import Path

import asyncpg

from app.core.config import REPO_ROOT, settings
from app.models.raw import CSV_TO_TABLE

CSV_DIR = REPO_ROOT / "datasets" / "raw"


async def load_all(dsn: str, csv_dir: Path) -> dict[str, int]:
    asyncpg_dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(asyncpg_dsn)
    try:
        async with conn.transaction():
            for filename, table in CSV_TO_TABLE.items():
                await conn.execute(f'TRUNCATE TABLE "{table.name}"')
                with open(csv_dir / filename, "rb") as source:
                    await conn.copy_to_table(table.name, source=source, format="csv", header=True)

        return {
            filename: await conn.fetchval(f'SELECT count(*) FROM "{table.name}"')
            for filename, table in CSV_TO_TABLE.items()
        }
    finally:
        await conn.close()


def main() -> None:
    counts = asyncio.run(load_all(settings.DATABASE_URL, CSV_DIR))
    for filename, count in counts.items():
        print(f"{filename}: {count} rows")


if __name__ == "__main__":
    main()
