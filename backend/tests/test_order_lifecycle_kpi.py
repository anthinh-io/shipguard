from datetime import date
from typing import Any

import pytest
from fake_risk import FakePredictor
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_predictor
from app.main import app
from app.services.dashboard import DashboardFilters, ReportingPeriod, compute_kpis
from app.services.users import create_user

pytestmark = pytest.mark.usefixtures("derived_data")

PASSWORD = "correct-horse-battery"
STAFF = "lifecycle-kpi-writer@shipguard.vn"

SELLER_A = "6560211a19b47992c3666cc44a7e94c0"
CATEGORY = "cama_mesa_banho"

# Ngoài phạm vi thời gian thật của dữ liệu Olist (kết thúc khoảng cuối 2018), nên kỳ báo
# cáo dựng riêng cho bài test này không lẫn đơn lịch sử nào — không cần lọc theo bang hay
# người bán để cô lập.
PURCHASED_AT = "2020-06-01T10:00:00+00:00"
ESTIMATED_DELIVERY_DATE = "2020-06-15"
DELIVERED_AT = "2020-06-20T09:00:00+00:00"
DELIVERED_DATE = date(2020, 6, 20)


@pytest.fixture
async def staff_id(auth_session: AsyncSession) -> int:
    return await create_user(
        auth_session,
        email=STAFF,
        password=PASSWORD,
        display_name="Người Kiểm KPI",
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


def _payload() -> dict[str, Any]:
    return {
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
            {"payment_type": "credit_card", "payment_installments": 1, "payment_value": 100.0}
        ],
    }


async def test_a_late_delivery_recorded_through_the_lifecycle_route_counts_as_late_in_the_kpis(
    client: AsyncClient, staff_id: int, session: AsyncSession
) -> None:
    app.dependency_overrides[get_predictor] = lambda: FakePredictor()
    headers = await bearer(client, STAFF)

    create_response = await client.post("/orders", json=_payload(), headers=headers)
    assert create_response.status_code == 201, create_response.text
    order_id = create_response.json()["order_id"]

    await client.post(
        f"/orders/{order_id}/milestones",
        json={"milestone": "payment_approved", "recorded_at": "2020-06-02T09:00:00+00:00"},
        headers=headers,
    )
    await client.post(
        f"/orders/{order_id}/milestones",
        json={"milestone": "handed_to_carrier", "recorded_at": "2020-06-05T09:00:00+00:00"},
        headers=headers,
    )
    delivered_response = await client.post(
        f"/orders/{order_id}/milestones",
        json={"milestone": "delivered_to_customer", "recorded_at": DELIVERED_AT},
        headers=headers,
    )
    assert delivered_response.status_code == 201, delivered_response.text

    # Kỳ dựng tường minh phủ đúng ngày giao, không qua resolve_default_period: ngưỡng
    # FULL_MONTH_MIN_DELIVERED_ORDERS (100) không đủ với một đơn test.
    period = ReportingPeriod(start_date=DELIVERED_DATE, end_date=DELIVERED_DATE)
    kpis = await compute_kpis(session, DashboardFilters(period=period))

    assert kpis.delivered_orders == 1
    assert kpis.late_orders == 1
