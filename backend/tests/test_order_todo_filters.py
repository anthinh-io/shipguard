import codecs
import csv
import io
from datetime import datetime, timezone
from typing import Any

import pytest
from fake_risk import FakePredictor
from httpx import AsyncClient
from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_predictor
from app.main import app
from app.models.risk import risk_assessments
from app.services.users import create_user

# #36: risk_level/handling_status trên /orders (và /orders/export) đều tính trên lần đánh
# giá mới nhất của đơn — cùng dữ liệu #35 đã dựng (Intervention). Không dùng derived_data
# (99.441 đơn Olist lịch sử, 0 dòng risk_assessments) để tạo đơn: mọi đơn ở đây phải tạo
# thật qua POST /orders để có lần đánh giá, đúng cách test_risk_assessment_route.py/
# test_intervention_route.py đã làm — tạo đơn cần current_user thật vì risk_assessments.
# created_by là khoá ngoại tới users.
pytestmark = pytest.mark.usefixtures("derived_data")

PASSWORD = "correct-horse-battery"
STAFF = "todo-filters-staff@shipguard.vn"

SELLER_A = "6560211a19b47992c3666cc44a7e94c0"
CATEGORY = "cama_mesa_banho"

# Đơn Olist lịch sử thật, không có Risk Assessment nào — cùng mã đơn với
# test_risk_assessment_route.py.
OLIST_ORDER_ID = "e481f51cbdc54678b7cc49136f2d6af7"

HIGH_RISK = 0.9
LOW_RISK = 0.05


@pytest.fixture
async def staff_id(auth_session: AsyncSession) -> int:
    return await create_user(
        auth_session,
        email=STAFF,
        password=PASSWORD,
        display_name="Người Lọc Việc Cần Làm",
        role="operations_staff",
    )


@pytest.fixture(autouse=True)
async def signed_in(client: AsyncClient, staff_id: int) -> None:
    response = await client.post(
        "/auth/login", json={"email": STAFF, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"


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


async def create_order(client: AsyncClient, *, late_probability: float) -> tuple[str, int]:
    app.dependency_overrides[get_predictor] = lambda: FakePredictor(
        late_probability=late_probability
    )
    response = await client.post("/orders", json=_payload())
    assert response.status_code == 201, response.text
    body = response.json()
    return body["order_id"], body["risk_assessment"]["id"]


async def record_intervention(client: AsyncClient, assessment_id: int) -> None:
    response = await client.post(
        f"/risk-assessments/{assessment_id}/intervention",
        json={"intervention": "other"},
    )
    assert response.status_code == 201, response.text


async def insert_second_assessment(
    session: AsyncSession, order_id: str, staff_id: int, *, is_high_risk: bool
) -> int:
    # #31 chưa có endpoint sinh lần đánh giá thứ hai qua HTTP trong phạm vi test này — chèn
    # thẳng, đúng cách test_risk_assessment_route.py đã làm để kiểm needs_handling.
    return await session.scalar(
        insert(risk_assessments)
        .values(
            order_id=order_id,
            checkpoint="payment_approved",
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


async def get_orders(client: AsyncClient, **params: Any) -> dict[str, Any]:
    response = await client.get("/orders", params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def order_ids(client: AsyncClient, **params: Any) -> set[str]:
    body = await get_orders(client, **params)
    return {item["order_id"] for item in body["items"]}


async def needs_handling(client: AsyncClient, order_id: str) -> bool:
    response = await client.get(f"/orders/{order_id}/risk-assessments")
    assert response.status_code == 200, response.text
    return any(row["needs_handling"] for row in response.json())


async def test_high_risk_unhandled_order_is_in_the_todo_filter(client: AsyncClient) -> None:
    order_id, _ = await create_order(client, late_probability=HIGH_RISK)

    body = await get_orders(client, risk_level="high", handling_status="unhandled")

    assert order_id in {item["order_id"] for item in body["items"]}
    assert {item["risk_level"] for item in body["items"]} == {"high"}


async def test_recording_an_intervention_moves_the_order_to_handled(
    client: AsyncClient,
) -> None:
    order_id, assessment_id = await create_order(client, late_probability=HIGH_RISK)
    assert order_id in await order_ids(client, risk_level="high", handling_status="unhandled")

    await record_intervention(client, assessment_id)

    assert order_id not in await order_ids(
        client, risk_level="high", handling_status="unhandled"
    )
    assert order_id in await order_ids(client, risk_level="high", handling_status="handled")


async def test_handled_then_a_new_high_risk_assessment_returns_to_unhandled(
    client: AsyncClient, staff_id: int, session: AsyncSession
) -> None:
    order_id, assessment_id = await create_order(client, late_probability=HIGH_RISK)
    await record_intervention(client, assessment_id)
    assert order_id in await order_ids(client, risk_level="high", handling_status="handled")

    await insert_second_assessment(session, order_id, staff_id, is_high_risk=True)
    await session.commit()

    # Lần đánh giá mới nhất chưa có Intervention riêng của nó — đây là việc cần làm mới,
    # rủi ro lần này có thể nằm ở khâu khác hẳn (CONTEXT.md, mục Handled).
    assert order_id in await order_ids(client, risk_level="high", handling_status="unhandled")
    assert order_id not in await order_ids(client, risk_level="high", handling_status="handled")


async def test_a_canceled_order_leaves_the_unhandled_filter(client: AsyncClient) -> None:
    order_id, _ = await create_order(client, late_probability=HIGH_RISK)
    assert order_id in await order_ids(client, risk_level="high", handling_status="unhandled")

    cancel = await client.post(f"/orders/{order_id}/cancellation")
    assert cancel.status_code == 201, cancel.text

    assert order_id not in await order_ids(client, handling_status="unhandled")
    # Vẫn hiện đúng rủi ro cao trên danh sách nói chung — chỉ biến mất khỏi "chưa xử lý".
    assert order_id in await order_ids(client, risk_level="high")


async def test_a_canceled_order_that_was_already_handled_stays_handled(
    client: AsyncClient,
) -> None:
    order_id, assessment_id = await create_order(client, late_probability=HIGH_RISK)
    await record_intervention(client, assessment_id)

    cancel = await client.post(f"/orders/{order_id}/cancellation")
    assert cancel.status_code == 201, cancel.text

    # Một Intervention đã ghi thì vẫn là đã ghi dù đơn sau đó bị hủy — chỉ nhánh "chưa xử
    # lý" loại đơn đã hủy, không phải nhánh "đã xử lý".
    assert order_id in await order_ids(client, handling_status="handled")


async def test_low_risk_order_stands_alone_in_unhandled_but_never_in_handled(
    client: AsyncClient,
) -> None:
    order_id, _ = await create_order(client, late_probability=LOW_RISK)

    body = await get_orders(client, order_id=order_id)
    assert body["items"][0]["risk_level"] == "low"

    # Đơn rủi ro thấp không bao giờ có Intervention (đường ghi chỉ nhận rủi ro cao), nên
    # theo định nghĩa trực giao đã chốt, nó luôn "chưa xử lý" khi lọc RIÊNG handling_status
    # — nhưng không bao giờ khớp risk_level=high, và không bao giờ vào "đã xử lý".
    assert order_id in await order_ids(client, handling_status="unhandled")
    assert order_id not in await order_ids(
        client, risk_level="high", handling_status="unhandled"
    )
    assert order_id not in await order_ids(client, handling_status="handled")


async def test_never_assessed_order_is_not_assessed_and_never_unhandled(
    client: AsyncClient,
) -> None:
    body = await get_orders(client, order_id=OLIST_ORDER_ID)
    assert body["items"][0]["risk_level"] == "not_assessed"

    assert OLIST_ORDER_ID not in await order_ids(client, handling_status="unhandled")
    assert OLIST_ORDER_ID not in await order_ids(client, handling_status="handled")


async def test_todo_filters_combine_with_existing_filters_sort_and_page(
    client: AsyncClient,
) -> None:
    order_id, _ = await create_order(client, late_probability=HIGH_RISK)

    body = await get_orders(
        client,
        risk_level="high",
        handling_status="unhandled",
        customer_state="SP",
        sort="purchased_at",
        direction="desc",
        page=1,
    )

    assert order_id in {item["order_id"] for item in body["items"]}


async def test_clearing_the_todo_filters_restores_the_previous_total(
    client: AsyncClient,
) -> None:
    await create_order(client, late_probability=HIGH_RISK)

    filtered = await get_orders(client, risk_level="high", handling_status="unhandled")
    cleared = await get_orders(client)

    assert cleared["total"] >= filtered["total"] > 0


async def test_todo_count_matches_needs_handling_across_orders(
    client: AsyncClient, staff_id: int, session: AsyncSession
) -> None:
    """Hợp đồng #36: tổng số đơn của risk_level=high + handling_status=unhandled phải bằng
    đúng số đơn đang có lần đánh giá là việc cần xử lý — cùng kiểu hợp đồng khớp số với
    drill-down bảng điều khiển (#25, test_drill_down_contract.py), ở đây đối chiếu hai
    đường thật: /orders (tập hợp theo đơn) và /orders/{id}/risk-assessments (needs_handling
    theo đơn).
    """
    # Phủ đủ các nhánh: rủi ro cao chưa xử lý (việc cần làm), đã xử lý, xử lý rồi có đánh
    # giá rủi ro cao mới (việc cần làm quay lại), rủi ro thấp, đã hủy.
    todo_order_id, _ = await create_order(client, late_probability=HIGH_RISK)
    handled_order_id, handled_assessment_id = await create_order(
        client, late_probability=HIGH_RISK
    )
    await record_intervention(client, handled_assessment_id)
    reopened_order_id, reopened_assessment_id = await create_order(
        client, late_probability=HIGH_RISK
    )
    await record_intervention(client, reopened_assessment_id)
    await insert_second_assessment(session, reopened_order_id, staff_id, is_high_risk=True)
    low_risk_order_id, _ = await create_order(client, late_probability=LOW_RISK)
    canceled_order_id, _ = await create_order(client, late_probability=HIGH_RISK)
    await session.commit()
    cancel = await client.post(f"/orders/{canceled_order_id}/cancellation")
    assert cancel.status_code == 201, cancel.text

    created_order_ids = [
        todo_order_id,
        handled_order_id,
        reopened_order_id,
        low_risk_order_id,
        canceled_order_id,
    ]

    needs_handling_ids = {
        order_id
        for order_id in created_order_ids
        if await needs_handling(client, order_id)
    }
    # Đúng hai đơn cần xử lý trong tập vừa dựng: todo_order_id và reopened_order_id.
    assert needs_handling_ids == {todo_order_id, reopened_order_id}

    todo_list = await get_orders(client, risk_level="high", handling_status="unhandled")
    todo_list_ids = {
        item["order_id"] for item in todo_list["items"] if item["order_id"] in created_order_ids
    }

    assert todo_list_ids == needs_handling_ids


async def test_csv_export_includes_the_risk_level_of_the_filtered_orders(
    client: AsyncClient,
) -> None:
    order_id, _ = await create_order(client, late_probability=HIGH_RISK)

    response = await client.get("/orders/export", params={"order_id": order_id})
    assert response.status_code == 200, response.text
    assert response.content.startswith(codecs.BOM_UTF8)
    text_body = response.content.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text_body, newline="")))

    header, data_row = rows[0], rows[1]
    assert "risk_level" in header
    assert data_row[header.index("order_id")] == order_id
    assert data_row[header.index("risk_level")] == "high"
