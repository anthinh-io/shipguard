import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.core.config import settings
from app.scripts.build_derived_data import build_all

EDGE_CASE_ORDERS = json.loads(
    (Path(__file__).parent / "fixtures" / "edge_case_orders.json").read_text("utf-8")
)

# Bọc ngoặc: mệnh đề này còn được dùng sau NOT, mà NOT kết chặt hơn AND.
DELIVERED = "(order_status = 'delivered' AND delivered_to_customer_at IS NOT NULL)"

ORDER_IDS = bindparam("ids", type_=sa.ARRAY(sa.Text))


@pytest.fixture
async def db(derived_data: dict[str, int]) -> AsyncIterator[AsyncConnection]:
    engine = create_async_engine(settings.TEST_DATABASE_URL)
    try:
        async with engine.connect() as connection:
            yield connection
    finally:
        await engine.dispose()


async def scalar(db: AsyncConnection, sql: str) -> int:
    return await db.scalar(text(sql))


async def test_estimated_delivery_date_is_stored_as_a_date(db: AsyncConnection) -> None:
    data_type = await db.scalar(
        text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = 'orders' "
            "AND column_name = 'estimated_delivery_date'"
        )
    )

    assert data_type == "date"


async def test_order_value_is_stored_as_an_exact_numeric(db: AsyncConnection) -> None:
    data_type = await db.scalar(
        text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = 'orders' AND column_name = 'order_value'"
        )
    )

    # Tiền cộng dồn qua nhiều dòng sản phẩm; kiểu số thực sẽ trôi xu và làm lệch
    # phép so với tổng thanh toán.
    assert data_type == "numeric"


async def test_every_order_is_present_with_its_status(db: AsyncConnection) -> None:
    assert await scalar(db, "SELECT count(*) FROM orders") == await scalar(
        db, "SELECT count(*) FROM raw_orders"
    )
    assert await scalar(db, "SELECT count(DISTINCT order_status) FROM orders") == 8
    assert await scalar(db, f"SELECT count(*) FROM orders WHERE NOT {DELIVERED}") > 0


async def test_delivered_orders_with_an_actual_delivery_date(
    db: AsyncConnection,
) -> None:
    assert await scalar(db, f"SELECT count(*) FROM orders WHERE {DELIVERED}") == 96470


async def test_late_orders_compare_calendar_dates_not_timestamps(
    db: AsyncConnection,
) -> None:
    late = await scalar(db, f"SELECT count(*) FROM orders WHERE {DELIVERED} AND is_late")
    # Phép so sai mà cờ is_late sinh ra để loại trừ, dựng lại ngay trên bảng này.
    late_by_timestamp = await scalar(
        db,
        f"SELECT count(*) FROM orders WHERE {DELIVERED} "
        "AND delivered_to_customer_at > estimated_delivery_date",
    )

    assert late == 6534
    assert late != 7826
    assert late_by_timestamp == 7826


async def test_low_review_orders_and_how_many_of_them_were_late(
    db: AsyncConnection,
) -> None:
    low_review = f"{DELIVERED} AND worst_review_score <= 2"

    assert await scalar(db, f"SELECT count(*) FROM orders WHERE {low_review}") == 12310
    assert (
        await scalar(db, f"SELECT count(*) FROM orders WHERE {low_review} AND is_late")
        == 3986
    )


async def test_orders_with_more_than_one_seller(db: AsyncConnection) -> None:
    multi_seller = await scalar(
        db,
        "SELECT count(*) FROM (SELECT order_id FROM order_sellers "
        "GROUP BY order_id HAVING count(*) > 1) t",
    )

    assert multi_seller == 1278


async def test_distinct_customer_states(db: AsyncConnection) -> None:
    assert await scalar(db, "SELECT count(DISTINCT customer_state) FROM orders") == 27


async def test_every_seller_is_present_with_its_city_and_state(
    db: AsyncConnection,
) -> None:
    # Con số lấy từ chính dữ liệu, không đóng cứng: tệp thô có 3.096 dòng kể cả tiêu
    # đề, nhưng đó là số dòng chứ không phải số mã phân biệt.
    assert await scalar(db, "SELECT count(*) FROM sellers") == await scalar(
        db, "SELECT count(DISTINCT seller_id) FROM raw_sellers"
    )
    assert await scalar(db, "SELECT count(*) FROM sellers") > 0
    # Seller State là bang người bán GỬI đi, khác tập bang khách nhận của orders —
    # nếu hai con số bằng nhau thì bài test không phân biệt được hai cột.
    assert await scalar(db, "SELECT count(DISTINCT seller_state) FROM sellers") == 23


@pytest.mark.parametrize(
    "index_name",
    [
        "ix_orders_delivered_to_customer_at",
        "ix_orders_customer_state",
        "ix_order_sellers_seller_id",
        "ix_orders_purchased_at",
        "ix_orders_order_id_prefix",
    ],
)
async def test_index_exists(db: AsyncConnection, index_name: str) -> None:
    assert await db.scalar(
        text("SELECT 1 FROM pg_indexes WHERE indexname = :name"), {"name": index_name}
    )


async def test_edge_case_fixture_loads_with_all_four_cases(db: AsyncConnection) -> None:
    every_id = sorted({o for group in EDGE_CASE_ORDERS.values() for o in group})
    rows = (
        await db.execute(
            text(
                "SELECT order_id, is_late, worst_review_score, payment_approval, "
                "seller_handling, carrier_transit FROM orders "
                "WHERE order_id = ANY(:ids)"
            ).bindparams(ORDER_IDS),
            {"ids": every_id},
        )
    ).all()
    facts = {row.order_id: row for row in rows}

    assert sorted(facts) == every_id

    # Giao đúng ngày cam kết là đúng hạn, bất kể mấy giờ.
    assert all(
        facts[o].is_late is False
        for o in EDGE_CASE_ORDERS["delivered_on_estimated_date"]
    )
    # Thiếu mốc trung gian thì khoảng thời gian rỗng, không phải bằng không. Thiếu mốc
    # nào trong hai mốc trung gian cũng đều làm seller_handling rỗng.
    assert all(
        facts[o].seller_handling is None
        for o in EDGE_CASE_ORDERS["missing_intermediate_milestone"]
    )
    # Không có đánh giá thì điểm rỗng, không phải bằng không.
    assert all(
        facts[o].worst_review_score is None for o in EDGE_CASE_ORDERS["no_review"]
    )

    multi_seller_ids = EDGE_CASE_ORDERS["multi_seller"]
    seller_counts = dict(
        (
            await db.execute(
                text(
                    "SELECT order_id, count(*) FROM order_sellers "
                    "WHERE order_id = ANY(:ids) GROUP BY order_id"
                ).bindparams(ORDER_IDS),
                {"ids": multi_seller_ids},
            )
        ).all()
    )

    assert all(seller_counts[o] > 1 for o in multi_seller_ids)


async def test_build_is_idempotent(derived_data: dict[str, int]) -> None:
    assert await build_all(settings.TEST_DATABASE_URL) == derived_data
