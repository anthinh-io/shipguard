import asyncio
from pathlib import Path

import asyncpg

from app.core.config import REPO_ROOT, settings

CSV_DIR = REPO_ROOT / "datasets" / "raw"

# Bảng tạm mang đúng tên chín bảng thô đã bị xoá, không phải tmp_*: nhờ thế bảy câu SQL
# dựng bên dưới không đổi một ký tự nào khi lớp thô rời khỏi lược đồ. Chúng là chỗ đã
# từng sai hai lần — đánh số thứ tự đánh giá và phép gộp Order Value — nên viết lại chúng
# là mở lại hai lỗi đã đóng. Postgres tra pg_temp trước cho tên bảng không kèm schema, nên
# cả COPY lẫn bảy câu SQL đều trúng bảng tạm.
#
# ON COMMIT DROP chứ không DROP tay ở cuối: giao dịch hỏng giữa chừng cũng không để lại
# bảng nào, và hai lần chạy chồng nhau trên hai kết nối không thấy bảng của nhau.
#
# Kiểu cột chép nguyên từ lớp thô cũ, không xê dịch: numeric(12,2) cho tiền — kiểu số thực
# sẽ trôi xu và làm lệch Order Value; integer cho customer_zip_code_prefix — chính vì nó
# mất số 0 đầu mà ORDERS_SQL phải lpad lại; timestamp cho các mốc thời gian, vì
# ORDER BY review_creation_date và phép ép ::date đều dựa vào đó.
RAW_TEMP_TABLES_SQL = """
    CREATE TEMP TABLE raw_customers (
        customer_id text, customer_unique_id text,
        customer_zip_code_prefix integer, customer_city text, customer_state text
    ) ON COMMIT DROP;
    CREATE TEMP TABLE raw_geolocation (
        geolocation_zip_code_prefix integer,
        geolocation_lat double precision, geolocation_lng double precision,
        geolocation_city text, geolocation_state text
    ) ON COMMIT DROP;
    CREATE TEMP TABLE raw_order_items (
        order_id text, order_item_id integer, product_id text, seller_id text,
        shipping_limit_date timestamp, price numeric(12, 2), freight_value numeric(12, 2)
    ) ON COMMIT DROP;
    CREATE TEMP TABLE raw_order_payments (
        order_id text, payment_sequential integer, payment_type text,
        payment_installments integer, payment_value numeric(12, 2)
    ) ON COMMIT DROP;
    CREATE TEMP TABLE raw_order_reviews (
        review_id text, order_id text, review_score integer,
        review_comment_title text, review_comment_message text,
        review_creation_date timestamp, review_answer_timestamp timestamp
    ) ON COMMIT DROP;
    CREATE TEMP TABLE raw_orders (
        order_id text, customer_id text, order_status text,
        order_purchase_timestamp timestamp, order_approved_at timestamp,
        order_delivered_carrier_date timestamp, order_delivered_customer_date timestamp,
        order_estimated_delivery_date timestamp
    ) ON COMMIT DROP;
    CREATE TEMP TABLE raw_products (
        product_id text, product_category_name text,
        product_name_lenght integer, product_description_lenght integer,
        product_photos_qty integer, product_weight_g integer,
        product_length_cm integer, product_height_cm integer, product_width_cm integer
    ) ON COMMIT DROP;
    CREATE TEMP TABLE raw_sellers (
        seller_id text, seller_zip_code_prefix integer,
        seller_city text, seller_state text
    ) ON COMMIT DROP;
    CREATE TEMP TABLE raw_product_category_name_translation (
        product_category_name text, product_category_name_english text
    ) ON COMMIT DROP;
"""

# raw_geolocation không câu SQL dựng nào đọc tới, nhưng vẫn nạp: danh sách này là ánh xạ
# trọn bộ chín tệp Olist, và bỏ một dòng ra sẽ thành câu hỏi "tệp kia đâu rồi" cho người
# đọc sau. Mô-đun huấn luyện đọc tệp toạ độ thẳng từ đĩa, không qua đây (ADR-0010).
CSV_TO_TABLE = {
    "olist_customers_dataset.csv": "raw_customers",
    "olist_geolocation_dataset.csv": "raw_geolocation",
    "olist_order_items_dataset.csv": "raw_order_items",
    "olist_order_payments_dataset.csv": "raw_order_payments",
    "olist_order_reviews_dataset.csv": "raw_order_reviews",
    "olist_orders_dataset.csv": "raw_orders",
    "olist_products_dataset.csv": "raw_products",
    "olist_sellers_dataset.csv": "raw_sellers",
    "product_category_name_translation.csv": "raw_product_category_name_translation",
}

# worst_review_score lấy min chứ không phải điểm mới nhất: một đơn có thể có nhiều
# dòng đánh giá với điểm khác nhau, và Low Review nghĩa là đã từng bị chấm 1–2 sao.
#
# customer_zip_code_prefix đệm lại cho đủ 5 chữ số: tệp CSV ghi "01310" nhưng cột trong
# bảng tạm là số nguyên nên đã nạp thành 1310.
ORDERS_SQL = """
    INSERT INTO orders (
        order_id,
        order_status,
        customer_state,
        customer_city,
        customer_zip_code_prefix,
        purchased_at,
        payment_approved_at,
        handed_to_carrier_at,
        delivered_to_customer_at,
        estimated_delivery_date,
        worst_review_score,
        order_value
    )
    SELECT
        o.order_id,
        o.order_status,
        c.customer_state,
        c.customer_city,
        lpad(c.customer_zip_code_prefix::text, 5, '0'),
        o.order_purchase_timestamp,
        o.order_approved_at,
        o.order_delivered_carrier_date,
        o.order_delivered_customer_date,
        o.order_estimated_delivery_date::date,
        r.worst_review_score,
        v.order_value
    FROM raw_orders o
    JOIN raw_customers c ON c.customer_id = o.customer_id
    LEFT JOIN (
        SELECT order_id, min(review_score) AS worst_review_score
        FROM raw_order_reviews
        GROUP BY order_id
    ) r ON r.order_id = o.order_id
    LEFT JOIN (
        SELECT order_id, sum(price + freight_value) AS order_value
        FROM raw_order_items
        GROUP BY order_id
    ) v ON v.order_id = o.order_id
"""

ORDER_SELLERS_SQL = """
    INSERT INTO order_sellers (order_id, seller_id)
    SELECT DISTINCT i.order_id, i.seller_id
    FROM raw_order_items i
    JOIN orders o ON o.order_id = i.order_id
"""

# DISTINCT chứ không phải SELECT trần: khoá chính seller_id sẽ từ chối bản sao, và một
# mã người bán lặp lại y hệt trong tệp thô là chuyện bình thường, không phải lỗi dữ liệu.
SELLERS_SQL = """
    INSERT INTO sellers (seller_id, seller_city, seller_state)
    SELECT DISTINCT seller_id, seller_city, seller_state
    FROM raw_sellers
"""

# JOIN orders y như ORDER_SELLERS_SQL: khoá ngoại không thể bị vi phạm, và dòng mồ côi trong
# dữ liệu thô rơi ra ở đây chứ không làm hỏng cả bước dựng.
ORDER_ITEMS_SQL = """
    INSERT INTO order_items (
        order_id,
        order_item_id,
        product_id,
        product_category_name,
        product_weight_g,
        price,
        freight_value,
        seller_id
    )
    SELECT
        i.order_id,
        i.order_item_id,
        i.product_id,
        p.product_category_name,
        p.product_weight_g,
        i.price,
        i.freight_value,
        i.seller_id
    FROM raw_order_items i
    JOIN orders o ON o.order_id = i.order_id
    LEFT JOIN raw_products p ON p.product_id = i.product_id
"""

ORDER_PAYMENTS_SQL = """
    INSERT INTO order_payments (
        order_id,
        payment_sequential,
        payment_type,
        payment_installments,
        payment_value
    )
    SELECT
        p.order_id,
        p.payment_sequential,
        p.payment_type,
        p.payment_installments,
        p.payment_value
    FROM raw_order_payments p
    JOIN orders o ON o.order_id = p.order_id
"""

# Sắp theo (ngày tạo, review_id) chứ không riêng ngày tạo: 157 cặp (order_id, ngày tạo) trùng
# nhau, còn bộ ba (order_id, ngày tạo, review_id) thì phân biệt tuyệt đối — dựng lại bao nhiêu
# lần cũng ra cùng một thứ tự.
ORDER_REVIEWS_SQL = """
    INSERT INTO order_reviews (
        order_id,
        review_sequential,
        review_score,
        comment_title,
        comment_message,
        review_created_at
    )
    SELECT
        r.order_id,
        row_number() OVER (
            PARTITION BY r.order_id
            ORDER BY r.review_creation_date, r.review_id
        ),
        r.review_score,
        r.review_comment_title,
        r.review_comment_message,
        r.review_creation_date
    FROM raw_order_reviews r
    JOIN orders o ON o.order_id = r.order_id
"""

# DISTINCT cùng lý do với SELLERS_SQL: khoá chính từ chối bản sao, mà một dòng lặp y hệt trong
# tệp thô không phải lỗi dữ liệu.
PRODUCT_CATEGORIES_SQL = """
    INSERT INTO product_categories (product_category_name, product_category_name_english)
    SELECT DISTINCT product_category_name, product_category_name_english
    FROM raw_product_category_name_translation
"""

DERIVED_TABLES = (
    "orders",
    "order_sellers",
    "order_items",
    "order_payments",
    "order_reviews",
    "sellers",
    "product_categories",
)


async def build_all(dsn: str, csv_dir: Path) -> dict[str, int]:
    asyncpg_dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(asyncpg_dsn)
    try:
        async with conn.transaction():
            await conn.execute(RAW_TEMP_TABLES_SQL)
            for filename, table in CSV_TO_TABLE.items():
                with open(csv_dir / filename, "rb") as source:
                    await conn.copy_to_table(table, source=source, format="csv", header=True)

            # Autovacuum không bao giờ đụng bảng tạm, nên thiếu câu này trình lập kế hoạch
            # ước mỗi bảng ~1000 dòng và chọn nested loop trên 112.650 dòng hàng — bước
            # dựng chậm đi hàng chục lần mà không có gì đỏ lên. Lớp thô cũ là bảng thường
            # nên đã được autovacuum phân tích sẵn; bảng tạm phải tự làm lấy.
            await conn.execute(f"ANALYZE {', '.join(CSV_TO_TABLE.values())}")

            # Khoá ngoại buộc xoá mọi bảng con trong cùng một câu lệnh; xoá riêng bảng
            # cha sẽ bị từ chối. Không dùng CASCADE — nó sẽ lan sang bảng khác nếu sau
            # này có bảng trỏ tới.
            #
            # Dựng câu lệnh thẳng từ DERIVED_TABLES thay vì viết tay danh sách thứ hai:
            # thêm một bảng dẫn xuất mà quên nó ở đây thì bước dựng sẽ nhân đôi dữ liệu
            # trong im lặng. Thứ tự trong câu TRUNCATE không quan trọng vì Postgres xoá
            # cả lượt; thứ tự INSERT thì có — orders phải có trước mọi bảng trỏ về nó.
            await conn.execute(f"TRUNCATE TABLE {', '.join(DERIVED_TABLES)}")
            await conn.execute(ORDERS_SQL)
            await conn.execute(ORDER_SELLERS_SQL)
            await conn.execute(ORDER_ITEMS_SQL)
            await conn.execute(ORDER_PAYMENTS_SQL)
            await conn.execute(ORDER_REVIEWS_SQL)
            await conn.execute(SELLERS_SQL)
            await conn.execute(PRODUCT_CATEGORIES_SQL)

        return {
            table: await conn.fetchval(f'SELECT count(*) FROM "{table}"')
            for table in DERIVED_TABLES
        }
    finally:
        await conn.close()


def main() -> None:
    counts = asyncio.run(build_all(settings.DATABASE_URL, CSV_DIR))
    for table, count in counts.items():
        print(f"{table}: {count} rows")


if __name__ == "__main__":
    main()
