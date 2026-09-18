from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
import sqlalchemy as sa
from fake_risk import FakePredictor
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_predictor
from app.core.config import settings
from app.main import app
from app.models.derived import orders
from app.risk.predictor import load_predictor
from app.services.users import create_user

pytestmark = pytest.mark.usefixtures("derived_data")

PASSWORD = "correct-horse-battery"
STAFF = "lifecycle-writer@shipguard.vn"

# Người bán thật của dữ liệu Olist, cùng mã với test_order_create_route.py.
SELLER_A = "6560211a19b47992c3666cc44a7e94c0"
CATEGORY = "cama_mesa_banho"

# Đơn Olist lịch sử thật, không có Risk Assessment nào — cùng mã đơn với
# test_risk_assessment_route.py.
OLIST_ORDER_ID = "e481f51cbdc54678b7cc49136f2d6af7"
MISSING_ORDER_ID = "00000000000000000000000000000000"

PURCHASED_AT = "2018-01-10T10:00:00+00:00"
ESTIMATED_DELIVERY_DATE = "2018-01-25"


@pytest.fixture
async def staff_id(auth_session: AsyncSession) -> int:
    return await create_user(
        auth_session,
        email=STAFF,
        password=PASSWORD,
        display_name="Người Vận Hành Vòng Đời",
        role="operations_staff",
    )


# Cùng lý do dọn dẹp với test_order_create_route.py: risk_assessments không có khoá
# ngoại tới orders, nên nó là nguồn duy nhất để tìm ra đơn do bộ test này tạo ra.
@pytest.fixture(autouse=True)
async def _cleanup_created_orders(session: AsyncSession):
    yield
    for table in ("order_items", "order_payments", "order_sellers", "orders"):
        await session.execute(
            text(
                f"DELETE FROM {table} WHERE order_id IN "
                "(SELECT order_id FROM risk_assessments)"
            )
        )
    await session.execute(text("DELETE FROM risk_assessments"))
    await session.commit()


def install_predictor(predictor: FakePredictor | None = None) -> None:
    app.dependency_overrides[get_predictor] = lambda: predictor or FakePredictor()


async def bearer(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _payload(
    *,
    purchased_at: str = PURCHASED_AT,
    estimated_delivery_date: str = ESTIMATED_DELIVERY_DATE,
) -> dict[str, Any]:
    return {
        "purchased_at": purchased_at,
        "estimated_delivery_date": estimated_delivery_date,
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
            {"payment_type": "credit_card", "payment_installments": 1, "payment_value": 100.0}
        ],
    }


async def _create_order(client: AsyncClient, headers: dict[str, str], **payload_kwargs) -> str:
    response = await client.post("/orders", json=_payload(**payload_kwargs), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["order_id"]


async def _record(
    client: AsyncClient, headers: dict[str, str], order_id: str, milestone: str, recorded_at: str
):
    return await client.post(
        f"/orders/{order_id}/milestones",
        json={"milestone": milestone, "recorded_at": recorded_at},
        headers=headers,
    )


# --- Đường vui ---------------------------------------------------------------


async def test_recording_payment_approved_updates_status_and_adds_an_assessment(
    client: AsyncClient, staff_id: int
) -> None:
    install_predictor()
    headers = await bearer(client, STAFF)
    order_id = await _create_order(client, headers)

    response = await _record(
        client, headers, order_id, "payment_approved", "2018-01-11T09:00:00+00:00"
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["order_id"] == order_id
    assert body["order_status"] == "approved"
    assert body["next_milestone"] == "handed_to_carrier"
    assert body["cancelable"] is True
    assert body["risk_assessment"] is not None
    assert body["risk_assessment"]["was_correct"] is None

    history = (await client.get(f"/orders/{order_id}/risk-assessments", headers=headers)).json()
    assert len(history) == 2


async def test_order_detail_reports_the_next_milestone_and_cancelable_flag(
    client: AsyncClient, staff_id: int
) -> None:
    install_predictor()
    headers = await bearer(client, STAFF)
    order_id = await _create_order(client, headers)

    response = await client.get(f"/orders/{order_id}", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["next_milestone"] == "payment_approved"
    assert response.json()["cancelable"] is True

    await _record(client, headers, order_id, "payment_approved", "2018-01-11T09:00:00+00:00")

    response = await client.get(f"/orders/{order_id}", headers=headers)
    assert response.json()["next_milestone"] == "handed_to_carrier"
    assert response.json()["cancelable"] is True


async def test_full_lifecycle_reconciles_every_assessment_on_delivery(
    client: AsyncClient, staff_id: int
) -> None:
    # 0.9 >= threshold_used (0.18) ở mọi lần đánh giá — is_high_risk luôn True.
    install_predictor(FakePredictor(late_probability=0.9))
    headers = await bearer(client, STAFF)
    order_id = await _create_order(client, headers)

    await _record(client, headers, order_id, "payment_approved", "2018-01-11T09:00:00+00:00")
    await _record(client, headers, order_id, "handed_to_carrier", "2018-01-12T09:00:00+00:00")
    # Sau ngày cam kết (2018-01-25) -> is_late True -> was_correct True vì is_high_risk cũng True.
    response = await _record(
        client, headers, order_id, "delivered_to_customer", "2018-01-30T09:00:00+00:00"
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["order_status"] == "delivered"
    assert body["next_milestone"] is None
    assert body["cancelable"] is False
    assert body["risk_assessment"] is None

    history = (await client.get(f"/orders/{order_id}/risk-assessments", headers=headers)).json()
    assert len(history) == 3
    assert all(row["was_correct"] is True for row in history)


async def test_reconciliation_treats_each_assessment_independently(
    client: AsyncClient, staff_id: int
) -> None:
    """Một đơn có cả đánh giá High Risk lẫn Low Risk trong lịch sử — khi giao trễ, chỉ
    đánh giá High Risk là đúng, các đánh giá Low Risk là sai, dù cùng một lần đối chiếu."""
    install_predictor(FakePredictor(late_probability=0.9))
    headers = await bearer(client, STAFF)
    order_id = await _create_order(client, headers)

    install_predictor(FakePredictor(late_probability=0.05))
    await _record(client, headers, order_id, "payment_approved", "2018-01-11T09:00:00+00:00")
    await _record(client, headers, order_id, "handed_to_carrier", "2018-01-12T09:00:00+00:00")

    # Sau ngày cam kết (2018-01-25) -> is_late True.
    response = await _record(
        client, headers, order_id, "delivered_to_customer", "2018-01-30T09:00:00+00:00"
    )
    assert response.status_code == 201, response.text

    history = (await client.get(f"/orders/{order_id}/risk-assessments", headers=headers)).json()
    assert len(history) == 3
    # FakePredictor không đổi checkpoint theo mốc (luôn "order_placed"), nên phân biệt
    # ba lần đánh giá bằng thứ tự — mới nhất trên cùng: [0]=handed_to_carrier,
    # [1]=payment_approved, [2]=order_placed (lúc tạo đơn).
    assert history[2]["is_high_risk"] is True
    assert history[2]["was_correct"] is True
    assert history[1]["is_high_risk"] is False
    assert history[1]["was_correct"] is False
    assert history[0]["is_high_risk"] is False
    assert history[0]["was_correct"] is False


async def test_editing_the_latest_milestone_adds_a_new_assessment_and_keeps_history(
    client: AsyncClient, staff_id: int
) -> None:
    install_predictor()
    headers = await bearer(client, STAFF)
    order_id = await _create_order(client, headers)
    await _record(client, headers, order_id, "payment_approved", "2018-01-11T09:00:00+00:00")

    response = await client.patch(
        f"/orders/{order_id}/milestones/payment_approved",
        json={"recorded_at": "2018-01-10T20:00:00+00:00"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["order_status"] == "approved"
    assert body["risk_assessment"] is not None

    # order_placed (tạo đơn) + payment_approved (ghi nhận) + payment_approved (sửa) —
    # dòng cũ vẫn còn, không bị ghi đè.
    history = (await client.get(f"/orders/{order_id}/risk-assessments", headers=headers)).json()
    assert len(history) == 3


async def test_canceling_an_order_updates_its_status(
    client: AsyncClient, staff_id: int
) -> None:
    install_predictor()
    headers = await bearer(client, STAFF)
    order_id = await _create_order(client, headers)

    response = await client.post(f"/orders/{order_id}/cancellation", headers=headers)

    assert response.status_code == 201, response.text
    assert response.json() == {"order_id": order_id, "order_status": "canceled"}


# --- 404 -----------------------------------------------------------------


async def test_recording_a_milestone_on_a_missing_order_answers_404(
    client: AsyncClient, staff_id: int
) -> None:
    install_predictor()
    headers = await bearer(client, STAFF)

    response = await _record(
        client, headers, MISSING_ORDER_ID, "payment_approved", "2018-01-11T09:00:00+00:00"
    )

    assert response.status_code == 404, response.text


async def test_canceling_a_missing_order_answers_404(client: AsyncClient, staff_id: int) -> None:
    headers = await bearer(client, STAFF)

    response = await client.post(f"/orders/{MISSING_ORDER_ID}/cancellation", headers=headers)

    assert response.status_code == 404, response.text


# --- 409: not_ship_guard_order ---------------------------------------------


async def test_recording_a_milestone_on_an_olist_order_is_rejected(
    client: AsyncClient, staff_id: int
) -> None:
    install_predictor()
    headers = await bearer(client, STAFF)

    response = await _record(
        client, headers, OLIST_ORDER_ID, "payment_approved", "2018-01-11T09:00:00+00:00"
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "not_ship_guard_order"


async def test_canceling_an_olist_order_is_rejected(client: AsyncClient, staff_id: int) -> None:
    headers = await bearer(client, STAFF)

    response = await client.post(f"/orders/{OLIST_ORDER_ID}/cancellation", headers=headers)

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "not_ship_guard_order"


# --- 409: already_delivered / already_canceled -----------------------------


async def test_recording_a_milestone_after_delivery_is_rejected(
    client: AsyncClient, staff_id: int
) -> None:
    install_predictor()
    headers = await bearer(client, STAFF)
    order_id = await _create_order(client, headers)
    await _record(client, headers, order_id, "payment_approved", "2018-01-11T09:00:00+00:00")
    await _record(client, headers, order_id, "handed_to_carrier", "2018-01-12T09:00:00+00:00")
    await _record(client, headers, order_id, "delivered_to_customer", "2018-01-20T09:00:00+00:00")

    response = await _record(
        client, headers, order_id, "payment_approved", "2018-01-21T09:00:00+00:00"
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "already_delivered"


async def test_canceling_a_delivered_order_is_rejected(
    client: AsyncClient, staff_id: int
) -> None:
    install_predictor()
    headers = await bearer(client, STAFF)
    order_id = await _create_order(client, headers)
    await _record(client, headers, order_id, "payment_approved", "2018-01-11T09:00:00+00:00")
    await _record(client, headers, order_id, "handed_to_carrier", "2018-01-12T09:00:00+00:00")
    await _record(client, headers, order_id, "delivered_to_customer", "2018-01-20T09:00:00+00:00")

    response = await client.post(f"/orders/{order_id}/cancellation", headers=headers)

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "already_delivered"


async def test_editing_a_milestone_after_delivery_is_rejected(
    client: AsyncClient, staff_id: int
) -> None:
    install_predictor()
    headers = await bearer(client, STAFF)
    order_id = await _create_order(client, headers)
    await _record(client, headers, order_id, "payment_approved", "2018-01-11T09:00:00+00:00")
    await _record(client, headers, order_id, "handed_to_carrier", "2018-01-12T09:00:00+00:00")
    await _record(client, headers, order_id, "delivered_to_customer", "2018-01-20T09:00:00+00:00")

    response = await client.patch(
        f"/orders/{order_id}/milestones/handed_to_carrier",
        json={"recorded_at": "2018-01-12T08:00:00+00:00"},
        headers=headers,
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "already_delivered"


async def test_recording_a_milestone_on_a_canceled_order_is_rejected(
    client: AsyncClient, staff_id: int
) -> None:
    install_predictor()
    headers = await bearer(client, STAFF)
    order_id = await _create_order(client, headers)
    await client.post(f"/orders/{order_id}/cancellation", headers=headers)

    response = await _record(
        client, headers, order_id, "payment_approved", "2018-01-11T09:00:00+00:00"
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "already_canceled"


async def test_canceling_an_already_canceled_order_is_rejected(
    client: AsyncClient, staff_id: int
) -> None:
    install_predictor()
    headers = await bearer(client, STAFF)
    order_id = await _create_order(client, headers)
    await client.post(f"/orders/{order_id}/cancellation", headers=headers)

    response = await client.post(f"/orders/{order_id}/cancellation", headers=headers)

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "already_canceled"


# --- 409: out_of_order_milestone / not_latest_milestone --------------------


async def test_recording_a_milestone_out_of_order_is_rejected(
    client: AsyncClient, staff_id: int
) -> None:
    install_predictor()
    headers = await bearer(client, STAFF)
    order_id = await _create_order(client, headers)

    response = await _record(
        client, headers, order_id, "handed_to_carrier", "2018-01-11T09:00:00+00:00"
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "out_of_order_milestone"


async def test_editing_a_milestone_that_is_not_the_latest_is_rejected(
    client: AsyncClient, staff_id: int
) -> None:
    install_predictor()
    headers = await bearer(client, STAFF)
    order_id = await _create_order(client, headers)

    response = await client.patch(
        f"/orders/{order_id}/milestones/payment_approved",
        json={"recorded_at": "2018-01-10T20:00:00+00:00"},
        headers=headers,
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "not_latest_milestone"


# --- 422 --------------------------------------------------------------------


async def test_recording_a_milestone_without_utc_offset_is_rejected(
    client: AsyncClient, staff_id: int
) -> None:
    install_predictor()
    headers = await bearer(client, STAFF)
    order_id = await _create_order(client, headers)

    response = await _record(
        client, headers, order_id, "payment_approved", "2018-01-11T09:00:00"
    )

    assert response.status_code == 422, response.text
    assert response.json()["detail"] == [
        {
            "type": "value_error",
            "loc": ["body", "recorded_at"],
            "msg": "recorded_at must include a UTC offset",
        }
    ]


async def test_recording_a_milestone_in_the_future_is_rejected(
    client: AsyncClient, staff_id: int
) -> None:
    install_predictor()
    headers = await bearer(client, STAFF)
    order_id = await _create_order(client, headers)
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    response = await _record(client, headers, order_id, "payment_approved", future)

    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["msg"] == "recorded_at cannot be in the future"


async def test_recording_a_milestone_before_the_previous_one_is_rejected(
    client: AsyncClient, staff_id: int
) -> None:
    install_predictor()
    headers = await bearer(client, STAFF)
    order_id = await _create_order(client, headers)

    response = await _record(
        client, headers, order_id, "payment_approved", "2018-01-09T09:00:00+00:00"
    )

    assert response.status_code == 422, response.text
    assert (
        response.json()["detail"][0]["msg"]
        == "recorded_at cannot be earlier than the previous milestone"
    )


# --- 503 ---------------------------------------------------------------------


async def test_missing_model_answers_503_and_changes_nothing(
    client: AsyncClient,
    staff_id: int,
    session: AsyncSession,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_predictor()
    headers = await bearer(client, STAFF)
    order_id = await _create_order(client, headers)

    # Đường vòng đời đọc mô hình thật, không FakePredictor, để chạm nhánh 503.
    app.dependency_overrides.pop(get_predictor, None)
    monkeypatch.setattr(settings, "RISK_MODEL_DIR", tmp_path)
    load_predictor.cache_clear()

    response = await _record(
        client, headers, order_id, "payment_approved", "2018-01-11T09:00:00+00:00"
    )

    assert response.status_code == 503, response.text
    order_status = await session.scalar(
        sa.select(orders.c.order_status).where(orders.c.order_id == order_id)
    )
    assert order_status == "created"
    load_predictor.cache_clear()
