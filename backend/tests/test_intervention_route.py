from datetime import datetime, timezone

import pytest
from fake_risk import FakePredictor
from httpx import AsyncClient
from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_predictor
from app.main import app
from app.models.risk import risk_assessments
from app.services.users import create_user, update_user

pytestmark = pytest.mark.usefixtures("derived_data")

PASSWORD = "correct-horse-battery"
STAFF = "intervention-staff@shipguard.vn"
MANAGER = "intervention-manager@shipguard.vn"
MISSING_ASSESSMENT_ID = 999_999_999

SELLER_A = "6560211a19b47992c3666cc44a7e94c0"
CATEGORY = "cama_mesa_banho"


@pytest.fixture
async def staff_id(auth_session: AsyncSession) -> int:
    return await create_user(
        auth_session,
        email=STAFF,
        password=PASSWORD,
        display_name="Người Xử Lý",
        role="operations_staff",
    )


@pytest.fixture
async def manager_id(auth_session: AsyncSession, staff_id: int) -> int:
    return await create_user(
        auth_session,
        email=MANAGER,
        password=PASSWORD,
        display_name="Người Quản Lý",
        role="logistics_manager",
    )


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


async def bearer(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _payload() -> dict:
    return {
        "purchased_at": "2018-01-10T10:00:00+00:00",
        "estimated_delivery_date": "2018-01-25",
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


async def _create_order(
    client: AsyncClient, headers: dict[str, str], *, late_probability: float
) -> tuple[str, int]:
    app.dependency_overrides[get_predictor] = lambda: FakePredictor(
        late_probability=late_probability
    )
    response = await client.post("/orders", json=_payload(), headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    return body["order_id"], body["risk_assessment"]["id"]


async def _insert_extra_assessment(
    session: AsyncSession, order_id: str, staff_id: int, *, is_high_risk: bool = True
) -> int:
    """Chèn tay một lần đánh giá thứ hai — cùng cách test_risk_assessment_route.py dùng để
    mô phỏng dòng sinh từ một mốc kế tiếp (#33 chưa có ở thời điểm viết #31)."""
    assessment_id = await session.scalar(
        insert(risk_assessments)
        .values(
            order_id=order_id,
            checkpoint="handed_to_carrier",
            late_probability=0.9 if is_high_risk else 0.05,
            is_high_risk=is_high_risk,
            threshold_used=0.18,
            model_version="fake-risk-model",
            risk_cause_stage="carrier_transit",
            carrier_transit_median_days=8.5,
            carrier_transit_historical_median_days=7.1,
            assessed_at=datetime.now(timezone.utc),
            created_by=staff_id,
        )
        .returning(risk_assessments.c.id)
    )
    await session.commit()
    return assessment_id


async def test_recording_intervention_marks_the_assessment_handled(
    client: AsyncClient, staff_id: int
) -> None:
    headers = await bearer(client, STAFF)
    order_id, assessment_id = await _create_order(client, headers, late_probability=0.9)

    response = await client.post(
        f"/risk-assessments/{assessment_id}/intervention",
        json={"intervention": "remind_seller"},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["needs_handling"] is False
    assert body["intervention"] == {
        "intervention": "remind_seller",
        "note": None,
        "handled_by": "Người Xử Lý",
        "handled_at": body["intervention"]["handled_at"],
    }

    history = await client.get(f"/orders/{order_id}/risk-assessments", headers=headers)
    assert history.json()[0]["needs_handling"] is False
    assert history.json()[0]["intervention"]["intervention"] == "remind_seller"


async def test_recording_intervention_with_note_is_returned(
    client: AsyncClient, staff_id: int
) -> None:
    headers = await bearer(client, STAFF)
    _, assessment_id = await _create_order(client, headers, late_probability=0.9)

    response = await client.post(
        f"/risk-assessments/{assessment_id}/intervention",
        json={"intervention": "change_carrier", "note": "  Đã đổi sang GHN.  "},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["intervention"]["note"] == "Đã đổi sang GHN."


async def test_a_new_high_risk_assessment_after_handling_is_a_new_item_to_handle(
    client: AsyncClient, staff_id: int, session: AsyncSession
) -> None:
    headers = await bearer(client, STAFF)
    order_id, first_id = await _create_order(client, headers, late_probability=0.9)

    handled = await client.post(
        f"/risk-assessments/{first_id}/intervention",
        json={"intervention": "remind_seller"},
        headers=headers,
    )
    assert handled.status_code == 201, handled.text

    second_id = await _insert_extra_assessment(session, order_id, staff_id)

    history = await client.get(f"/orders/{order_id}/risk-assessments", headers=headers)
    by_id = {row["id"]: row for row in history.json()}
    # Dòng cũ đã xử lý VÀ đã bị thay thế: không còn là việc cần xử lý, dòng mới là việc mới.
    assert by_id[first_id]["needs_handling"] is False
    assert by_id[second_id]["needs_handling"] is True

    # Đã xử lý rồi thì không ghi lại được nữa, dù lý do thật sự (cũng) là đã bị thay thế —
    # already_handled được chẩn đoán trước assessment_superseded.
    retry = await client.post(
        f"/risk-assessments/{first_id}/intervention",
        json={"intervention": "other"},
        headers=headers,
    )
    assert retry.status_code == 409
    assert retry.json()["detail"]["code"] == "already_handled"


async def test_recording_intervention_on_a_superseded_never_handled_assessment_is_rejected(
    client: AsyncClient, staff_id: int, session: AsyncSession
) -> None:
    headers = await bearer(client, STAFF)
    order_id, first_id = await _create_order(client, headers, late_probability=0.9)
    await _insert_extra_assessment(session, order_id, staff_id)

    response = await client.post(
        f"/risk-assessments/{first_id}/intervention",
        json={"intervention": "remind_seller"},
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "assessment_superseded"


async def test_recording_intervention_on_low_risk_assessment_is_rejected(
    client: AsyncClient, staff_id: int
) -> None:
    headers = await bearer(client, STAFF)
    _, assessment_id = await _create_order(client, headers, late_probability=0.05)

    response = await client.post(
        f"/risk-assessments/{assessment_id}/intervention",
        json={"intervention": "remind_seller"},
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "not_high_risk"


async def test_recording_intervention_on_canceled_order_is_rejected(
    client: AsyncClient, staff_id: int
) -> None:
    headers = await bearer(client, STAFF)
    order_id, assessment_id = await _create_order(client, headers, late_probability=0.9)
    cancel_response = await client.post(f"/orders/{order_id}/cancellation", headers=headers)
    assert cancel_response.status_code == 201, cancel_response.text

    response = await client.post(
        f"/risk-assessments/{assessment_id}/intervention",
        json={"intervention": "remind_seller"},
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "order_canceled"


async def test_intervention_of_a_locked_handler_still_shows_their_name(
    client: AsyncClient, staff_id: int, manager_id: int, auth_session: AsyncSession
) -> None:
    headers = await bearer(client, STAFF)
    order_id, assessment_id = await _create_order(client, headers, late_probability=0.9)
    handled = await client.post(
        f"/risk-assessments/{assessment_id}/intervention",
        json={"intervention": "notify_customer"},
        headers=headers,
    )
    assert handled.status_code == 201, handled.text

    await update_user(
        auth_session,
        actor_role="logistics_manager",
        user_id=staff_id,
        is_locked=True,
    )

    response = await client.get(
        f"/orders/{order_id}/risk-assessments", headers=await bearer(client, MANAGER)
    )

    assert response.json()[0]["intervention"]["handled_by"] == "Người Xử Lý"


async def test_an_assessment_can_only_be_handled_once(
    client: AsyncClient, staff_id: int
) -> None:
    headers = await bearer(client, STAFF)
    _, assessment_id = await _create_order(client, headers, late_probability=0.9)
    first = await client.post(
        f"/risk-assessments/{assessment_id}/intervention",
        json={"intervention": "remind_seller"},
        headers=headers,
    )
    assert first.status_code == 201, first.text

    second = await client.post(
        f"/risk-assessments/{assessment_id}/intervention",
        json={"intervention": "other"},
        headers=headers,
    )

    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "already_handled"


async def test_intervention_must_be_one_of_the_fixed_list(
    client: AsyncClient, staff_id: int
) -> None:
    headers = await bearer(client, STAFF)
    _, assessment_id = await _create_order(client, headers, late_probability=0.9)

    response = await client.post(
        f"/risk-assessments/{assessment_id}/intervention",
        json={"intervention": "bribe_the_carrier"},
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.parametrize("length,expected_status", [(2000, 201), (2001, 422)])
async def test_intervention_note_length_limit(
    client: AsyncClient, staff_id: int, length: int, expected_status: int
) -> None:
    headers = await bearer(client, STAFF)
    _, assessment_id = await _create_order(client, headers, late_probability=0.9)

    response = await client.post(
        f"/risk-assessments/{assessment_id}/intervention",
        json={"intervention": "other", "note": "a" * length},
        headers=headers,
    )

    assert response.status_code == expected_status


async def test_recording_intervention_requires_login(client: AsyncClient, staff_id: int) -> None:
    headers = await bearer(client, STAFF)
    _, assessment_id = await _create_order(client, headers, late_probability=0.9)

    response = await client.post(
        f"/risk-assessments/{assessment_id}/intervention",
        json={"intervention": "remind_seller"},
    )

    assert response.status_code == 401


async def test_unknown_assessment_id_answers_404(client: AsyncClient, staff_id: int) -> None:
    headers = await bearer(client, STAFF)

    response = await client.post(
        f"/risk-assessments/{MISSING_ASSESSMENT_ID}/intervention",
        json={"intervention": "remind_seller"},
        headers=headers,
    )

    assert response.status_code == 404
