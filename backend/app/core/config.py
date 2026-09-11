from pathlib import Path
from typing import Annotated

from pydantic import BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


def use_asyncpg_driver(value: str) -> str:
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+asyncpg://", 1)
    return value


AsyncPostgresDsn = Annotated[str, BeforeValidator(use_asyncpg_driver)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    PROJECT_NAME: str
    DATABASE_URL: AsyncPostgresDsn
    TEST_DATABASE_URL: AsyncPostgresDsn


settings = Settings()
