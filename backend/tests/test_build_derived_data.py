import json
import re
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import sqlalchemy as sa
from olist_csv import read_rows, row_count
from sqlalchemy import bindparam, insert, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine

from conftest import rebuild_derived_data

from app.core.config import settings
from app.models.risk import risk_assessments
from app.scripts.build_derived_data import (
    CSV_DIR,
    DERIVED_TABLES,
    RISK_ASSESSMENTS_EXIST_ERROR,
    build_all,
)
from app.services.users import create_user

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
    assert await scalar(db, "SELECT count(*) FROM orders") == row_count(
        "olist_orders_dataset.csv"
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


async def test_every_order_has_a_shipping_city_and_a_five_digit_zip_prefix(
    db: AsyncConnection,
) -> None:
    # Cột trong bảng tạm là số nguyên nên mất số 0 đầu: 01310 nạp vào thành 1310. Bảng
    # dẫn xuất phải trả lại đủ 5 chữ số, nếu không mã bưu chính của cả vùng São Paulo
    # hiện sai.
    assert await scalar(db, "SELECT count(*) FROM orders WHERE customer_city IS NULL") == 0
    assert (
        await scalar(
            db,
            "SELECT count(*) FROM orders WHERE customer_zip_code_prefix !~ '^[0-9]{5}$'",
        )
        == 0
    )
    assert (
        await scalar(db, "SELECT count(*) FROM orders WHERE customer_zip_code_prefix LIKE '0%'")
        > 0
    )


async def test_every_seller_is_present_with_its_city_and_state(
    db: AsyncConnection,
) -> None:
    # Con số lấy từ chính tệp CSV, không đóng cứng: tệp có 3.096 dòng kể cả tiêu đề,
    # nhưng đó là số dòng chứ không phải số mã phân biệt.
    distinct_sellers = len(
        {row["seller_id"] for row in read_rows("olist_sellers_dataset.csv")}
    )
    assert await scalar(db, "SELECT count(*) FROM sellers") == distinct_sellers
    assert await scalar(db, "SELECT count(*) FROM sellers") > 0
    # Seller State là bang người bán GỬI đi, khác tập bang khách nhận của orders —
    # nếu hai con số bằng nhau thì bài test không phân biệt được hai cột.
    assert await scalar(db, "SELECT count(DISTINCT seller_state) FROM sellers") == 23


# Danh sách ngắn đi ba mục so với trước, không phải mất độ phủ: ba chỉ mục
# ix_raw_*_order_id đã biến mất cùng chín bảng thô ở migration 0010. Bảng tạm dựng trong
# bước dựng không mang chỉ mục nào — có ANALYZE rồi thì trình lập kế hoạch chọn hash join.
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


async def test_line_tables_match_the_golden_counts(db: AsyncConnection) -> None:
    assert await scalar(db, "SELECT count(*) FROM order_items") == 112650
    assert await scalar(db, "SELECT count(*) FROM order_payments") == 103886
    # order_sellers là bảng dẫn xuất duy nhất chưa có ai ghim tổng số dòng: bài đếm đơn
    # nhiều người bán ở trên chỉ nhìn phần đuôi, nên bảng này mất dòng vẫn xanh.
    assert await scalar(db, "SELECT count(*) FROM order_sellers") == 100010


async def test_every_csv_review_row_becomes_a_numbered_review_line(
    db: AsyncConnection,
) -> None:
    assert await scalar(db, "SELECT count(*) FROM order_reviews") == row_count(
        "olist_order_reviews_dataset.csv"
    )
    # Cộng thêm con số vàng viết tay: phép so trên bám theo tệp CSV, nên nó vẫn xanh nếu
    # có ai thay tệp bằng một tệp ngắn hơn.
    assert await scalar(db, "SELECT count(*) FROM order_reviews") == 99224
    # 547 đơn có nhiều hơn một đánh giá. Con số này về 0 nghĩa là cột thứ tự mất tác dụng
    # và bảng đang âm thầm bỏ bớt dòng.
    assert (
        await scalar(
            db,
            "SELECT count(*) FROM (SELECT order_id FROM order_reviews "
            "GROUP BY order_id HAVING count(*) > 1) t",
        )
        == 547
    )
    # Thứ tự liền mạch từ 1: max phải bằng đúng số dòng của chính đơn đó.
    assert (
        await scalar(
            db,
            "SELECT count(*) FROM (SELECT order_id FROM order_reviews GROUP BY order_id "
            "HAVING max(review_sequential) <> count(*) OR min(review_sequential) <> 1) t",
        )
        == 0
    )


async def test_orders_paid_with_more_than_one_payment_line(db: AsyncConnection) -> None:
    assert (
        await scalar(
            db,
            "SELECT count(*) FROM (SELECT order_id FROM order_payments "
            "GROUP BY order_id HAVING count(*) > 1) t",
        )
        == 2961
    )


async def test_product_lines_keep_the_original_category_and_the_weight(
    db: AsyncConnection,
) -> None:
    # Dòng sản phẩm lưu tên danh mục GỐC; nhãn tiếng Anh tra ở product_categories lúc đọc.
    assert (
        await scalar(db, "SELECT count(*) FROM order_items WHERE product_category_name IS NULL")
        == 1603
    )
    assert await scalar(db, "SELECT count(*) FROM order_items WHERE product_weight_g IS NULL") == 18


async def test_the_category_lookup_covers_every_translated_category(
    db: AsyncConnection,
) -> None:
    assert await scalar(db, "SELECT count(*) FROM product_categories") == 71
    # Đúng hai danh mục chưa có bản dịch — pc_gamer và
    # portateis_cozinha_e_preparadores_de_alimentos — trải trên 24 dòng sản phẩm. Ghim con
    # số thay vì chỉ đòi lớn hơn 0: bảng tra mất 50 danh mục thì phép so lỏng vẫn xanh.
    # Các dòng đó vẫn hiện tên gốc nhờ coalesce ở đường đọc, còn ô chọn danh mục thì không
    # nên mời chọn chúng.
    untranslated = (
        "FROM order_items i WHERE i.product_category_name IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM product_categories c "
        "WHERE c.product_category_name = i.product_category_name)"
    )

    assert await scalar(db, f"SELECT count(*) {untranslated}") == 24
    assert await scalar(db, f"SELECT count(DISTINCT i.product_category_name) {untranslated}") == 2


async def test_build_is_idempotent(derived_data: dict[str, int]) -> None:
    # Bảy tên viết thẳng ra chứ không đọc lại DERIVED_TABLES: build_all dựng từ điển TỪ
    # chính tuple đó, nên so hai thứ ấy với nhau là luôn đúng dù ai có rút bớt bảng nào.
    # Danh sách viết tay ở đây mới là thứ đỏ lên khi bước dựng bỏ sót một bảng.
    assert set(derived_data) == {
        "orders",
        "order_sellers",
        "order_items",
        "order_payments",
        "order_reviews",
        "sellers",
        "product_categories",
    }
    assert set(DERIVED_TABLES) == set(derived_data)
    assert await rebuild_derived_data(settings.TEST_DATABASE_URL) == derived_data


async def test_seller_zip_code_prefix_matches_csv_with_leading_zeros(
    db: AsyncConnection,
) -> None:
    # Cùng phép kiểm với customer_zip_code_prefix: cột tạm là số nguyên nên đã làm mất số 0
    # đầu, và SELLERS_SQL phải lpad lại — đối chiếu thẳng CSV để không tự lừa chính mình.
    csv_zips = {
        row["seller_id"]: row["seller_zip_code_prefix"]
        for row in read_rows("olist_sellers_dataset.csv")
    }
    rows = await db.execute(text("SELECT seller_id, seller_zip_code_prefix FROM sellers"))
    db_zips = {row.seller_id: row.seller_zip_code_prefix for row in rows}

    assert db_zips == csv_zips
    assert all(len(zip_code) == 5 for zip_code in db_zips.values())


async def test_build_refuses_to_run_once_a_risk_assessment_exists(
    auth_session: AsyncSession, derived_data: dict[str, int]
) -> None:
    # ADR-0007 việc 3 / ADR-0010 việc 4: một Risk Assessment là dấu hiệu có đơn tạo trong
    # Ship Guard, và TRUNCATE của build_all sẽ xoá mất đơn đó không hoàn tác được. Dùng
    # build_all trực tiếp (không cờ) vì đây chính là hành vi mặc định đang bị kiểm.
    user_id = await create_user(
        auth_session,
        email="build-guard@shipguard.vn",
        password="correct-horse-battery",
        display_name="Build Guard",
        role="operations_staff",
    )
    await auth_session.execute(
        insert(risk_assessments).values(
            order_id="deadbeefdeadbeefdeadbeefdeadbeef",
            checkpoint="order_placed",
            late_probability=0.5,
            is_high_risk=False,
            threshold_used=0.18,
            model_version="test",
            risk_cause_stage="carrier_transit",
            created_by=user_id,
        )
    )
    await auth_session.commit()

    engine = create_async_engine(settings.TEST_DATABASE_URL)
    try:
        async with engine.connect() as connection:
            before = await connection.scalar(text("SELECT count(*) FROM orders"))

            with pytest.raises(RuntimeError, match=re.escape(RISK_ASSESSMENTS_EXIST_ERROR)):
                await build_all(settings.TEST_DATABASE_URL, CSV_DIR)

            after = await connection.scalar(text("SELECT count(*) FROM orders"))
            assert after == before
    finally:
        await engine.dispose()

    # Dọn lại: risk_assessments không được auth_session xoá tự động sau mỗi test (chỉ xoá
    # lúc VÀO), và các bài chạy sau trong cùng phiên không phải bài nào cũng đi qua
    # auth_session để được dọn hộ.
    await auth_session.execute(text("TRUNCATE risk_assessments"))
    await auth_session.commit()
