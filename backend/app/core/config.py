from pathlib import Path
from typing import Annotated

from pydantic import BeforeValidator, Field
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


def anchor_to_repo_root(value: str | Path) -> Path:
    """Đường dẫn tương đối tính từ gốc repo, không phải từ thư mục đang đứng.

    `.env` nằm ở gốc repo nên `./models` đọc tự nhiên là `<gốc repo>/models`. Để nó
    bám theo thư mục hiện hành thì cùng một cấu hình trỏ đi hai nơi khác nhau tuỳ chỗ
    gọi — backend chạy từ gốc repo tìm thấy mô hình, còn notebook chạy từ thư mục của
    nó thì không.
    """
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


RepoPath = Annotated[Path, BeforeValidator(anchor_to_repo_root)]


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
    # Thư mục lệnh huấn luyện ghi tệp mô hình và báo cáo; backend đọc lại từ đây.
    # Thiếu tệp không làm backend chết — xem get_predictor trong api/deps.py.
    RISK_MODEL_DIR: RepoPath
    # Ngưỡng Late Probability để một đơn là High Risk. Lấy từ báo cáo đánh giá chứ
    # không đặt theo cảm tính (ADR-0008). Chặn cả 0 lẫn 1 vì hai đầu đều vô nghĩa:
    # 0 là mọi đơn rủi ro cao, 1 là không đơn nào.
    RISK_THRESHOLD: Annotated[float, Field(gt=0.0, lt=1.0)]
    # Chỉ đọc khi chưa có Super Admin nào — xem ensure_super_admin.
    SUPER_ADMIN_EMAIL: str
    SUPER_ADMIN_PASSWORD: str
    SUPER_ADMIN_NAME: str


settings = Settings()
