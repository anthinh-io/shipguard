from pathlib import Path

import pytest
import sqlalchemy as sa
from fake_risk import FakePredictor
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_predictor
from app.core.config import settings
from app.core.security import create_access_token
from app.main import app
from app.models.risk import risk_assessments
from app.services.users import create_user

pytestmark = pytest.mark.usefixtures("derived_data")

PASSWORD = "correct-horse-battery"
STAFF = "model-metrics-writer@shipguard.vn"

# Người bán thật của dữ liệu Olist, cùng mã với test_order_lifecycle_route.py.
SELLER_A = "6560211a19b47992c3666cc44a7e94c0"
CATEGORY = "cama_mesa_banho"

PURCHASED_AT = "2018-01-10T10:00:00+00:00"
ESTIMATED_DELIVERY_DATE = "2018-01-25"


# staff_id phụ thuộc auth_session, vốn TRUNCATE risk_assessments (cùng users/order_notes/...)
# ngay trước khi trả về — mọi bài dùng staff_id vì vậy luôn bắt đầu với bảng đối chiếu rỗng,
# không cần bài này tự dọn thêm. Dọn thêm một lần nữa (như bản trước của tệp này từng làm)
# chỉ tạo thêm một engine giữ khoá trên cùng bảng đúng lúc TRUNCATE của bài kế tiếp cần khoá
# đó — nguồn của các lần treo/treo ngẫu nhiên đã gặp khi chạy cùng bộ test đầy đủ.
@pytest.fixture
async def staff_id(auth_session: AsyncSession) -> int:
    return await create_user(
        auth_session,
        email=STAFF,
        password=PASSWORD,
        display_name="Người Viết Chỉ Số Mô Hình",
        role="operations_staff",
    )


# Chỉ một bài (hủy đơn) tạo đơn thật qua API. Dọn đúng mã đơn đã capture được, không dò qua
# risk_assessments — mã hủy đơn giả (created_by giả) không cần bảng đó còn nguyên để tìm ra.
@pytest.fixture
def created_order_ids() -> list[str]:
    return []


@pytest.fixture(autouse=True)
async def _cleanup_created_orders(session: AsyncSession, created_order_ids: list[str]):
    yield
    if not created_order_ids:
        return
    for table in ("order_items", "order_payments", "order_sellers", "orders"):
        await session.execute(
            sa.text(f"DELETE FROM {table} WHERE order_id = ANY(:ids)"),
            {"ids": created_order_ids},
        )
    await session.commit()


@pytest.fixture
def model_dir(monkeypatch: pytest.MonkeyPatch):
    def point_at(path: Path) -> Path:
        monkeypatch.setattr(settings, "RISK_MODEL_DIR", path)
        return path

    return point_at


@pytest.fixture(autouse=True)
def _clear_predictor_override():
    yield
    app.dependency_overrides.pop(get_predictor, None)


def headers_for(user_id: int, role: str = "operations_staff") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id, role, [])}"}


async def _insert_assessment(
    session: AsyncSession,
    *,
    order_id: str,
    checkpoint: str,
    is_high_risk: bool,
    was_correct: bool | None,
    created_by: int,
) -> None:
    await session.execute(
        sa.insert(risk_assessments).values(
            order_id=order_id,
            checkpoint=checkpoint,
            late_probability=0.9 if is_high_risk else 0.05,
            is_high_risk=is_high_risk,
            threshold_used=0.5,
            model_version="test-model",
            risk_cause_stage="carrier_transit",
            was_correct=was_correct,
            created_by=created_by,
        )
    )
    await session.commit()


def _reconciliation_row(body: dict, checkpoint: str) -> dict:
    return next(row for row in body["reconciliation"] if row["checkpoint"] == checkpoint)


# --- Đăng nhập / vai trò -------------------------------------------------------


async def test_requires_login(client: AsyncClient) -> None:
    response = await client.get("/model-metrics")
    assert response.status_code == 401


async def test_any_role_can_view(
    client: AsyncClient, staff_id: int, tmp_path: Path, model_dir
) -> None:
    model_dir(tmp_path)

    response = await client.get("/model-metrics", headers=headers_for(staff_id))

    assert response.status_code == 200


# --- Báo cáo huấn luyện ---------------------------------------------------------


async def test_untrained_reports_not_trained(
    client: AsyncClient, staff_id: int, tmp_path: Path, model_dir
) -> None:
    model_dir(tmp_path)

    response = await client.get("/model-metrics", headers=headers_for(staff_id))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["trained"] is False
    assert body["report"] is None
    assert len(body["reconciliation"]) == 3
    assert all(row["total"] == 0 for row in body["reconciliation"])
    # Mẫu rỗng vẫn là mẫu nhỏ — is_small_sample(0) là True.
    assert all(row["small_sample"] for row in body["reconciliation"])


async def test_trained_report_shape(
    client: AsyncClient, staff_id: int, risk_model_dir: Path, model_dir
) -> None:
    model_dir(risk_model_dir)

    response = await client.get("/model-metrics", headers=headers_for(staff_id))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["trained"] is True
    report = body["report"]
    assert set(report["algorithms"]) == {"xgboost_quantile", "xgboost_aft", "sklearn_quantile"}
    for evaluation in report["algorithms"].values():
        for checkpoint in ("order_placed", "payment_approved", "handed_to_carrier"):
            scored = evaluation[checkpoint]
            assert set(scored) == {"precision", "recall", "f1"}
            assert all(0.0 <= scored[name] <= 1.0 for name in ("precision", "recall", "f1"))
    assert report["selected_algorithm"] in report["algorithms"]
    assert isinstance(report["meets_f1_target"], bool)
    # Ngưỡng "đang áp dụng" là cấu hình đang chạy, không phải ngưỡng đề xuất trong báo cáo —
    # hai giá trị có thể lệch nếu ai đó huấn luyện lại mà chưa cập nhật .env.
    assert body["risk_threshold"] == settings.RISK_THRESHOLD


# --- Đối chiếu tích lũy ----------------------------------------------------------
#
# staff_id đảm bảo risk_assessments rỗng lúc vào bài (xem ghi chú ở fixture) nên các bài
# dưới đây khẳng định thẳng vào tổng, không cần tính hiệu trước/sau.


async def test_reconciliation_counts_and_rates(
    client: AsyncClient, session: AsyncSession, staff_id: int, tmp_path: Path, model_dir
) -> None:
    model_dir(tmp_path)
    # Ở mốc payment_approved: 2 lần đúng khi High Risk (TP), 1 lần sai khi High Risk (FP),
    # 1 lần sai khi Low Risk (FN), 1 lần đúng khi Low Risk (TN).
    combos = [(True, True), (True, True), (True, False), (False, False), (False, True)]
    for index, (is_high_risk, was_correct) in enumerate(combos):
        await _insert_assessment(
            session,
            order_id=f"model-metrics-rate-{index}",
            checkpoint="payment_approved",
            is_high_risk=is_high_risk,
            was_correct=was_correct,
            created_by=staff_id,
        )

    response = await client.get("/model-metrics", headers=headers_for(staff_id))

    assert response.status_code == 200, response.text
    row = _reconciliation_row(response.json(), "payment_approved")
    assert row["total"] == 5
    assert row["correct"] == 3  # 2 TP + 1 TN
    assert row["incorrect"] == 2  # 1 FP + 1 FN
    assert row["precision"] == pytest.approx(2 / 3)  # TP / (TP + FP)
    assert row["recall"] == pytest.approx(2 / 3)  # TP / (TP + FN)
    assert row["small_sample"] is True  # 5 < 30, cùng ngưỡng với is_small_sample


async def test_reconciliation_ignores_rows_not_yet_reconciled(
    client: AsyncClient, session: AsyncSession, staff_id: int, tmp_path: Path, model_dir
) -> None:
    model_dir(tmp_path)
    await _insert_assessment(
        session,
        order_id="model-metrics-pending",
        checkpoint="order_placed",
        is_high_risk=True,
        was_correct=None,
        created_by=staff_id,
    )

    response = await client.get("/model-metrics", headers=headers_for(staff_id))

    row = _reconciliation_row(response.json(), "order_placed")
    assert row["total"] == 0


async def test_canceled_orders_are_not_counted_in_reconciliation(
    client: AsyncClient,
    staff_id: int,
    tmp_path: Path,
    model_dir,
    created_order_ids: list[str],
) -> None:
    """Đơn hủy không bao giờ nhận mốc delivered_to_customer, nên was_correct của nó mãi
    là NULL — WHERE was_correct IS NOT NULL đã tự loại nó, không cần lọc order_status
    riêng (xem order_lifecycle.record_milestone)."""
    model_dir(tmp_path)
    app.dependency_overrides[get_predictor] = lambda: FakePredictor()
    headers = headers_for(staff_id)
    order = await client.post(
        "/orders",
        json={
            "purchased_at": PURCHASED_AT,
            "estimated_delivery_date": ESTIMATED_DELIVERY_DATE,
            "customer_state": "SP",
            "customer_city": "Sao Paulo",
            "customer_zip_code_prefix": "01310",
            "items": [
                {
                    "seller_id": SELLER_A,
                    "product_category_name": CATEGORY,
                    "product_weight_g": 500,
                    "price": 100.0,
                    "freight_value": 15.0,
                }
            ],
            "payments": [
                {
                    "payment_type": "credit_card",
                    "payment_installments": 1,
                    "payment_value": 100.0,
                }
            ],
        },
        headers=headers,
    )
    assert order.status_code == 201, order.text
    order_id = order.json()["order_id"]
    created_order_ids.append(order_id)
    cancellation = await client.post(f"/orders/{order_id}/cancellation", headers=headers)
    assert cancellation.status_code == 201, cancellation.text

    response = await client.get("/model-metrics", headers=headers)

    row = _reconciliation_row(response.json(), "order_placed")
    assert row["total"] == 0


async def test_small_sample_flag_reflects_the_total(
    client: AsyncClient, session: AsyncSession, staff_id: int, tmp_path: Path, model_dir
) -> None:
    # Ranh giới chính xác (29/30) của is_small_sample đã kiểm ở
    # test_dashboard_service.py::test_small_sample_threshold_excludes_exactly_thirty — hàm
    # đó dùng lại nguyên, không định nghĩa ngưỡng riêng. Bài này chỉ kiểm phần việc của
    # route: có bám đúng is_small_sample(total) hay không.
    model_dir(tmp_path)
    for index in range(2):
        await _insert_assessment(
            session,
            order_id=f"model-metrics-small-{index}",
            checkpoint="handed_to_carrier",
            is_high_risk=True,
            was_correct=True,
            created_by=staff_id,
        )

    response = await client.get("/model-metrics", headers=headers_for(staff_id))

    row = _reconciliation_row(response.json(), "handed_to_carrier")
    assert row["total"] == 2
    assert row["small_sample"] is True
