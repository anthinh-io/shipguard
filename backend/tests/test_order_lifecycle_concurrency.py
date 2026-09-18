"""Ba thao tác vòng đời (record/edit/cancel) chạy đua nhau trên cùng một đơn.

Không dùng asyncio.gather thô: thứ tự "ai thắng" khi đó phụ thuộc lịch chạy của event
loop, nên một lần chạy có thể không hề chạm nhánh WHERE-không-khớp đang muốn kiểm.
Thay vào đó, một phiên (B) giữ transaction mở sau khi UPDATE (chưa commit) để khoá dòng
ở phía Postgres; phiên kia (A) đọc dữ liệu CŨ rồi bị chặn thật sự ở chính câu UPDATE có
điều kiện cho tới khi B thoát ra (commit) — tái hiện đúng kịch bản "đọc trước khi đơn
đổi trạng thái, ghi sau khi đơn đã đổi trạng thái" một cách tất định, không phụ thuộc
may rủi lịch chạy.
"""

import asyncio
from datetime import datetime

import pytest
import sqlalchemy as sa
from fake_risk import FakePredictor
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_predictor
from app.core.config import settings
from app.main import app
from app.models.derived import orders
from app.models.risk import risk_assessments
from app.services import order_lifecycle
from app.services.users import create_user

pytestmark = pytest.mark.usefixtures("derived_data")

PASSWORD = "correct-horse-battery"
STAFF = "lifecycle-race@shipguard.vn"

SELLER_A = "6560211a19b47992c3666cc44a7e94c0"
CATEGORY = "cama_mesa_banho"
PURCHASED_AT = "2018-01-10T10:00:00+00:00"
ESTIMATED_DELIVERY_DATE = "2018-01-25"


@pytest.fixture
async def staff_id(auth_session: AsyncSession) -> int:
    return await create_user(
        auth_session,
        email=STAFF,
        password=PASSWORD,
        display_name="Người Kiểm Tra Đua Tranh",
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


async def _create_order(client: AsyncClient, headers: dict[str, str]) -> str:
    app.dependency_overrides[get_predictor] = lambda: FakePredictor()
    response = await client.post(
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
                {"payment_type": "credit_card", "payment_installments": 1, "payment_value": 100.0}
            ],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["order_id"]


async def _bearer(client: AsyncClient) -> dict[str, str]:
    response = await client.post("/auth/login", json={"email": STAFF, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class _SecondSession:
    """Một AsyncSession độc lập, engine riêng — mô phỏng một request thứ hai chạy đua."""

    async def __aenter__(self) -> AsyncSession:
        self._engine = create_async_engine(settings.TEST_DATABASE_URL)
        self._session = async_sessionmaker(self._engine, expire_on_commit=False)()
        return self._session

    async def __aexit__(self, *exc_info: object) -> None:
        await self._session.close()
        await self._engine.dispose()


async def test_recording_a_milestone_loses_to_a_concurrent_cancel(
    client: AsyncClient, staff_id: int, session: AsyncSession
) -> None:
    """B (hủy) commit trước; A (ghi mốc) đã đọc "created" từ trước đó nhưng bị chặn ở
    chính câu UPDATE có điều kiện cho tới khi B nhả khoá — phải nhận OrderAlreadyCanceledError,
    không được âm thầm hồi sinh đơn đã hủy về "approved"."""
    headers = await _bearer(client)
    order_id = await _create_order(client, headers)

    async with _SecondSession() as session_a:
        async with session.begin():
            # B giữ khoá dòng bằng chính câu UPDATE hủy đơn thật (đúng đường code sản
            # xuất), nhưng chưa commit.
            await session.execute(
                sa.update(orders)
                .where(orders.c.order_id == order_id)
                .values(order_status="canceled")
            )

            record_task = asyncio.create_task(
                order_lifecycle.record_milestone(
                    session_a,
                    FakePredictor(),
                    order_id,
                    order_lifecycle.RecordMilestone(
                        milestone="payment_approved",
                        recorded_at=datetime.fromisoformat("2018-01-11T09:00:00+00:00"),
                    ),
                    staff_id,
                )
            )
            # Đủ thời gian để A hoàn tất SELECT (đọc "created", trước khi B commit) và
            # tới lượt chờ khoá dòng ở chính câu UPDATE.
            await asyncio.sleep(0.2)
        # Thoát khối `async with session.begin()` -> commit -> nhả khoá cho A.

        with pytest.raises(order_lifecycle.OrderAlreadyCanceledError):
            await record_task

    order_status, payment_approved_at = (
        await session.execute(
            sa.select(orders.c.order_status, orders.c.payment_approved_at).where(
                orders.c.order_id == order_id
            )
        )
    ).one()
    assert order_status == "canceled"
    assert payment_approved_at is None


async def test_editing_a_milestone_loses_to_a_concurrent_advance(
    client: AsyncClient, staff_id: int, session: AsyncSession
) -> None:
    """B (ghi nhận handed_to_carrier) commit trước, đẩy đơn qua khỏi payment_approved; A
    (sửa giờ payment_approved) đã đọc đơn từ trước đó nhưng bị chặn ở chính câu UPDATE có
    điều kiện — phải nhận NotLatestMilestoneError, không được âm thầm sửa đè và sinh một
    Risk Assessment tính sai chặng."""
    headers = await _bearer(client)
    order_id = await _create_order(client, headers)
    await order_lifecycle.record_milestone(
        session,
        FakePredictor(),
        order_id,
        order_lifecycle.RecordMilestone(
            milestone="payment_approved",
            recorded_at=datetime.fromisoformat("2018-01-11T09:00:00+00:00"),
        ),
        staff_id,
    )

    async with _SecondSession() as session_a:
        async with session.begin():
            await session.execute(
                sa.update(orders)
                .where(orders.c.order_id == order_id)
                .values(
                    handed_to_carrier_at=datetime.fromisoformat("2018-01-12T09:00:00"),
                    order_status="shipped",
                )
            )

            edit_task = asyncio.create_task(
                order_lifecycle.edit_milestone(
                    session_a,
                    FakePredictor(),
                    order_id,
                    "payment_approved",
                    order_lifecycle.EditMilestoneTimestamp(
                        recorded_at=datetime.fromisoformat("2018-01-10T20:00:00+00:00")
                    ),
                    staff_id,
                )
            )
            await asyncio.sleep(0.2)

        with pytest.raises(order_lifecycle.NotLatestMilestoneError):
            await edit_task

    payment_approved_at = await session.scalar(
        sa.select(orders.c.payment_approved_at).where(orders.c.order_id == order_id)
    )
    # Giờ payment_approved_at không đổi theo A — vẫn đúng giá trị record_milestone đã ghi
    # ban đầu (09:00), không phải giá trị 20:00 mà A định sửa.
    assert payment_approved_at == datetime.fromisoformat("2018-01-11T09:00:00")

    history_count = await session.scalar(
        sa.select(sa.func.count())
        .select_from(risk_assessments)
        .where(risk_assessments.c.order_id == order_id)
    )
    # order_placed (tạo đơn) + payment_approved (record_milestone trước đua tranh) — B
    # đẩy handed_to_carrier bằng UPDATE thô nên không sinh dòng nào, và A bị chặn nên
    # cũng không sinh dòng thừa nào.
    assert history_count == 2
