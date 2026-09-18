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
from app.models.derived import order_items, order_payments, orders
from app.models.risk import risk_assessments
from app.risk.predictor import load_predictor
from app.services.users import create_user

pytestmark = pytest.mark.usefixtures("derived_data")

PASSWORD = "correct-horse-battery"
STAFF = "order-writer@shipguard.vn"

# Hai người bán thật trong dữ liệu Olist — busiest_seller và mục đầu small_sample_sellers
# của tests/fixtures/edge_case_filters.json, không phải mã bịa.
SELLER_A = "6560211a19b47992c3666cc44a7e94c0"
SELLER_B = "0015a82c2db000af6aaaf3ae2ecb0532"
# Danh mục phổ biến nhất của dữ liệu Olist (3.029 sản phẩm) — chắc chắn có trong
# product_categories.
CATEGORY = "cama_mesa_banho"


@pytest.fixture
async def staff_id(auth_session: AsyncSession) -> int:
    return await create_user(
        auth_session,
        email=STAFF,
        password=PASSWORD,
        display_name="Người Viết Đơn",
        role="operations_staff",
    )


# Bảng risk_assessments không có khoá ngoại tới orders (xem app/models/risk.py), nên nó
# là nguồn duy nhất để tìm ra đơn do chính bộ test này tạo ra mà dọn lại — thiếu bước này
# thì số đơn 99.441 mà các bài test khác canh sẽ đội lên.
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


def install_predictor(predictor: FakePredictor) -> None:
    app.dependency_overrides[get_predictor] = lambda: predictor


async def bearer(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _items(seller_ids: tuple[str, ...], **item_overrides: Any) -> list[dict[str, Any]]:
    items = [
        {
            "seller_id": seller_id,
            "product_category_name": CATEGORY,
            "product_weight_g": 500,
            "price": 100.0,
            "freight_value": 15.0,
        }
        for seller_id in seller_ids
    ]
    if item_overrides:
        items[0] = {**items[0], **item_overrides}
    return items


def _payload(
    seller_ids: tuple[str, ...],
    *,
    purchased_at: str = "2018-01-10T10:00:00+00:00",
    estimated_delivery_date: str = "2018-01-25",
    customer_state: str = "SP",
    payment_type: str = "credit_card",
    payment_installments: int = 1,
    item_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "purchased_at": purchased_at,
        "estimated_delivery_date": estimated_delivery_date,
        "customer_state": customer_state,
        "customer_city": "Sao Paulo",
        "customer_zip_code_prefix": "01310",
        "items": _items(seller_ids, **(item_overrides or {})),
        "payments": [
            {
                "payment_type": payment_type,
                "payment_installments": payment_installments,
                "payment_value": 100.0 * len(seller_ids),
            }
        ],
    }


async def _counts(session: AsyncSession) -> dict[str, int]:
    return {
        name: await session.scalar(sa.select(sa.func.count()).select_from(table))
        for name, table in (
            ("orders", orders),
            ("order_items", order_items),
            ("order_payments", order_payments),
            ("risk_assessments", risk_assessments),
        )
    }


async def test_creating_an_order_writes_the_order_and_its_first_assessment(
    client: AsyncClient, staff_id: int
) -> None:
    install_predictor(FakePredictor(late_probability=0.05))

    response = await client.post(
        "/orders", json=_payload((SELLER_A, SELLER_B)), headers=await bearer(client, STAFF)
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["order_id"]) == 32
    assert all(char in "0123456789abcdef" for char in body["order_id"])
    assessment = body["risk_assessment"]
    assert assessment["checkpoint"] == "order_placed"
    assert assessment["late_probability"] == pytest.approx(0.05)
    assert assessment["is_high_risk"] is False
    assert assessment["model_version"] == "fake-risk-model"


async def test_high_risk_assessment_names_the_cause_and_its_excess_days(
    client: AsyncClient, staff_id: int
) -> None:
    install_predictor(
        FakePredictor(
            late_probability=0.9, risk_cause_stage="carrier_transit", excess_days=3.5
        )
    )

    response = await client.post(
        "/orders", json=_payload((SELLER_A,)), headers=await bearer(client, STAFF)
    )

    assert response.status_code == 201, response.text
    assessment = response.json()["risk_assessment"]
    assert assessment["is_high_risk"] is True
    cause = assessment["risk_cause"]
    assert cause["stage"] == "carrier_transit"
    assert cause["seller_id"] is None
    assert cause["median_days"] - cause["historical_median_days"] == pytest.approx(3.5)


async def test_high_risk_seller_cause_names_the_slowest_seller(
    client: AsyncClient, staff_id: int
) -> None:
    install_predictor(
        FakePredictor(
            late_probability=0.9,
            risk_cause_stage="seller_handling",
            risk_cause_seller_id=SELLER_B,
            excess_days=2.0,
        )
    )

    response = await client.post(
        "/orders", json=_payload((SELLER_A, SELLER_B)), headers=await bearer(client, STAFF)
    )

    assert response.status_code == 201, response.text
    cause = response.json()["risk_assessment"]["risk_cause"]
    assert cause["stage"] == "seller_handling"
    assert cause["seller_id"] == SELLER_B


async def test_low_risk_hides_no_cause_field_but_stays_low(
    client: AsyncClient, staff_id: int
) -> None:
    # Rủi ro thấp vẫn được ghi nhận nguyên nhân trong cơ sở dữ liệu (dùng cho #37), chỉ
    # không hiển thị ở khối rủi ro của #32 — is_high_risk là cờ biểu mẫu dựa vào.
    install_predictor(FakePredictor(late_probability=0.01))

    response = await client.post(
        "/orders", json=_payload((SELLER_A,)), headers=await bearer(client, STAFF)
    )

    assert response.status_code == 201, response.text
    assert response.json()["risk_assessment"]["is_high_risk"] is False


async def test_created_order_is_findable_in_the_order_list(
    client: AsyncClient, staff_id: int
) -> None:
    install_predictor(FakePredictor())
    headers = await bearer(client, STAFF)
    create_response = await client.post(
        "/orders", json=_payload((SELLER_A,)), headers=headers
    )
    order_id = create_response.json()["order_id"]

    response = await client.get("/orders", params={"order_id": order_id}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["order_id"] == order_id


INVALID_PAYLOADS: dict[str, dict[str, Any]] = {
    "no product lines": {**_payload((SELLER_A,)), "items": []},
    "seller does not exist": {
        **_payload((SELLER_A,)),
        "items": _items((SELLER_A,), seller_id="00000000000000000000000000000000"),
    },
    "category does not exist": {
        **_payload((SELLER_A,)),
        "items": _items((SELLER_A,), product_category_name="does_not_exist"),
    },
    "state outside the known list": {**_payload((SELLER_A,)), "customer_state": "ZZ"},
    "multiple installments without a credit card": {
        **_payload((SELLER_A,)),
        "payments": [
            {"payment_type": "boleto", "payment_installments": 3, "payment_value": 100.0}
        ],
    },
    "purchased_at in the future": {
        **_payload((SELLER_A,)),
        "purchased_at": "2099-01-01T00:00:00+00:00",
    },
    "estimated_delivery_date before purchase": {
        **_payload((SELLER_A,)),
        "estimated_delivery_date": "2018-01-01",
    },
    "negative price": {
        **_payload((SELLER_A,)),
        "items": _items((SELLER_A,), price=-1.0),
    },
}


@pytest.mark.parametrize(
    ("label", "payload"), INVALID_PAYLOADS.items(), ids=list(INVALID_PAYLOADS)
)
async def test_invalid_order_data_saves_nothing(
    client: AsyncClient,
    staff_id: int,
    session: AsyncSession,
    label: str,
    payload: dict[str, Any],
) -> None:
    install_predictor(FakePredictor())
    before = await _counts(session)

    response = await client.post(
        "/orders", json=payload, headers=await bearer(client, STAFF)
    )

    assert response.status_code == 422, response.text
    assert await _counts(session) == before


async def test_missing_model_answers_503_and_creates_nothing(
    client: AsyncClient,
    staff_id: int,
    session: AsyncSession,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Không cài FakePredictor: route phải đi qua get_predictor thật để chạm nhánh 503.
    app.dependency_overrides.pop(get_predictor, None)
    monkeypatch.setattr(settings, "RISK_MODEL_DIR", tmp_path)
    load_predictor.cache_clear()
    before = await _counts(session)

    # Payload hợp lệ hoàn toàn: nếu sai một trường thì 422 có thể chặn trước và bài test
    # xanh vì lý do khác, không phải vì thiếu mô hình.
    response = await client.post(
        "/orders", json=_payload((SELLER_A,)), headers=await bearer(client, STAFF)
    )

    assert response.status_code == 503, response.text
    assert await _counts(session) == before
    load_predictor.cache_clear()


async def test_product_categories_are_listed_with_labels(
    client: AsyncClient, staff_id: int
) -> None:
    response = await client.get("/product-categories", headers=await bearer(client, STAFF))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 71
    assert {"name": CATEGORY, "label": "bed_bath_table"} in body


async def test_product_categories_requires_login(client: AsyncClient) -> None:
    response = await client.get("/product-categories")

    assert response.status_code == 401
