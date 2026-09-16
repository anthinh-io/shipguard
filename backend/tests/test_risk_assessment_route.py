from datetime import datetime, timezone

import pytest
from fake_risk import FakePredictor
from httpx import AsyncClient
from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_predictor
from app.main import app
from app.models.risk import risk_assessments
from app.services.users import create_user

pytestmark = pytest.mark.usefixtures("derived_data")

PASSWORD = "correct-horse-battery"
STAFF = "risk-history-reader@shipguard.vn"

# Đơn Olist lịch sử thật, không có Risk Assessment nào — cùng mã đơn với
# test_order_notes_route.py.
OLIST_ORDER_ID = "e481f51cbdc54678b7cc49136f2d6af7"
MISSING_ORDER_ID = "00000000000000000000000000000000"

SELLER_A = "6560211a19b47992c3666cc44a7e94c0"
CATEGORY = "cama_mesa_banho"


@pytest.fixture
async def staff_id(auth_session: AsyncSession) -> int:
    return await create_user(
        auth_session,
        email=STAFF,
        password=PASSWORD,
        display_name="Người Đọc Lịch Sử",
        role="operations_staff",
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


async def test_history_lists_newest_assessment_first(
    client: AsyncClient, staff_id: int, session: AsyncSession
) -> None:
    app.dependency_overrides[get_predictor] = lambda: FakePredictor(late_probability=0.05)
    headers = await bearer(client, STAFF)
    create_response = await client.post("/orders", json=_payload(), headers=headers)
    order_id = create_response.json()["order_id"]
    first_assessment_id = create_response.json()["risk_assessment"]["id"]

    # #31 chưa có endpoint sinh lần đánh giá thứ hai (thuộc #33) — chèn thẳng để kiểm thứ
    # tự đọc, đúng cách test_build_derived_data.py đã làm để kiểm chốt chặn.
    second_assessment_id = await session.scalar(
        insert(risk_assessments)
        .values(
            order_id=order_id,
            checkpoint="payment_approved",
            late_probability=0.9,
            is_high_risk=True,
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

    response = await client.get(f"/orders/{order_id}/risk-assessments", headers=headers)

    assert response.status_code == 200
    ids = [row["id"] for row in response.json()]
    assert ids == [second_assessment_id, first_assessment_id]


async def test_olist_order_has_no_assessment_history(client: AsyncClient, staff_id: int) -> None:
    headers = await bearer(client, STAFF)

    response = await client.get(
        f"/orders/{OLIST_ORDER_ID}/risk-assessments", headers=headers
    )

    assert response.status_code == 200
    assert response.json() == []


async def test_unknown_order_id_answers_404(client: AsyncClient, staff_id: int) -> None:
    headers = await bearer(client, STAFF)

    response = await client.get(
        f"/orders/{MISSING_ORDER_ID}/risk-assessments", headers=headers
    )

    assert response.status_code == 404


async def test_history_requires_login(client: AsyncClient) -> None:
    response = await client.get(f"/orders/{OLIST_ORDER_ID}/risk-assessments")

    assert response.status_code == 401
