from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_predictor
from app.core.config import settings
from app.core.security import create_access_token
from app.main import warm_risk_predictor
from app.risk.predictor import MODEL_FILENAME, RiskPredictor, load_predictor

pytestmark = pytest.mark.usefixtures("derived_data")


# maxsize=1 nghĩa là bài chạy sau đẩy bài chạy trước ra khỏi đệm, nên không dọn thì
# thứ tự chạy quyết định kết quả. Cùng loại lỗi mà fixture auth_session đã phải
# TRUNCATE để tránh.
@pytest.fixture(autouse=True)
def clear_predictor_cache() -> Iterator[None]:
    load_predictor.cache_clear()
    yield
    load_predictor.cache_clear()


@pytest.fixture
def model_dir(monkeypatch: pytest.MonkeyPatch):
    def point_at(path: Path) -> Path:
        monkeypatch.setattr(settings, "RISK_MODEL_DIR", path)
        return path

    return point_at


class FakePredictor:
    model_version = "fake-0000"


# Một ứng dụng nhỏ dựng ngay trong bài test thay vì gắn route vào app thật: tiêu chí
# chấp nhận chỉ đòi thay được bộ dự đoán bằng bản giả mà không phải khởi động máy chủ,
# còn gắn route vào app dùng chung thì bài này để lại rác cho mọi bài khác.
def _app_using_predictor() -> FastAPI:
    application = FastAPI()

    @application.get("/needs-model")
    def needs_model(predictor=Depends(get_predictor)):
        return {"model_version": predictor.model_version}

    return application


async def _call(application: FastAPI) -> tuple[int, dict]:
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.get("/needs-model")
    return response.status_code, response.json()


async def test_a_fake_predictor_can_replace_the_real_one_without_a_server() -> None:
    application = _app_using_predictor()
    application.dependency_overrides[get_predictor] = lambda: FakePredictor()

    status, body = await _call(application)

    assert status == 200
    assert body == {"model_version": "fake-0000"}


async def test_trained_model_is_served_through_the_dependency(
    risk_model_dir: Path, model_dir
) -> None:
    model_dir(risk_model_dir)

    status, body = await _call(_app_using_predictor())

    assert status == 200
    assert body["model_version"] == RiskPredictor.load(risk_model_dir).model_version


async def test_missing_model_answers_503_rather_than_crashing(
    tmp_path: Path, model_dir
) -> None:
    model_dir(tmp_path)

    status, body = await _call(_app_using_predictor())

    assert status == 503
    assert body == {"detail": "Risk model is not available"}


async def test_half_written_model_file_answers_503_not_500(
    tmp_path: Path, model_dir
) -> None:
    # Dạng "thiếu mô hình" hay gặp nhất trong thực tế không phải thư mục rỗng mà là một
    # lần huấn luyện bị ngắt giữa chừng. Tệp hỏng mà trả 500 thì nhìn như backend hỏng.
    (tmp_path / MODEL_FILENAME).write_bytes(b"not a joblib file")
    model_dir(tmp_path)

    status, body = await _call(_app_using_predictor())

    assert status == 503
    assert body == {"detail": "Risk model is not available"}


async def test_dashboard_and_orders_still_work_without_any_model(
    client: AsyncClient, tmp_path: Path, model_dir
) -> None:
    """Khác có chủ đích so với quy tắc khởi động hiện có.

    Thiếu tài khoản quản trị thì máy chủ dừng hẳn; thiếu tệp mô hình thì không, vì
    bảng điều khiển và tra cứu đơn phải dùng được ngay cả khi chưa huấn luyện lần nào.
    """
    model_dir(tmp_path)
    warm_risk_predictor()  # không được ném lỗi dù thư mục rỗng

    client.headers["Authorization"] = (
        f"Bearer {create_access_token(1, 'operations_staff', [])}"
    )

    assert (await client.get("/dashboard")).status_code == 200
    assert (await client.get("/orders")).status_code == 200
