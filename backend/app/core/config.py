from pathlib import Path
from typing import Annotated

from pydantic import BeforeValidator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


def use_asyncpg_driver(value: str) -> str:
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+asyncpg://", 1)
    return value


AsyncPostgresDsn = Annotated[str, BeforeValidator(use_asyncpg_driver)]


def split_on_commas(value: str | list[str]) -> list[str]:
    if isinstance(value, str):
        return [origin.strip() for origin in value.split(",") if origin.strip()]
    return value


# Danh sách phân tách bằng dấu phẩy. NoDecode là bắt buộc chứ không phải trang trí:
# thiếu nó, pydantic-settings cố đọc mọi kiểu phức hợp trong tệp môi trường bằng JSON
# và hỏng trước khi validator kịp chạy — buộc .env phải viết `["http://..."]`.
OriginList = Annotated[list[str], NoDecode, BeforeValidator(split_on_commas)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    PROJECT_NAME: str
    DATABASE_URL: AsyncPostgresDsn
    TEST_DATABASE_URL: AsyncPostgresDsn
    CORS_ALLOWED_ORIGINS: OriginList
    JWT_SECRET_KEY: str
    # Chỉ đọc khi chưa có Super Admin nào — xem ensure_super_admin.
    SUPER_ADMIN_EMAIL: str
    SUPER_ADMIN_PASSWORD: str
    SUPER_ADMIN_NAME: str


settings = Settings()
