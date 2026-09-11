import asyncio

import asyncpg

from app.core.config import settings

# worst_review_score lấy min chứ không phải điểm mới nhất: một đơn có thể có nhiều
# dòng đánh giá với điểm khác nhau, và Low Review nghĩa là đã từng bị chấm 1–2 sao.
ORDERS_SQL = """
    INSERT INTO orders (
        order_id,
        order_status,
        customer_state,
        purchased_at,
        payment_approved_at,
        handed_to_carrier_at,
        delivered_to_customer_at,
        estimated_delivery_date,
        worst_review_score
    )
    SELECT
        o.order_id,
        o.order_status,
        c.customer_state,
        o.order_purchase_timestamp,
        o.order_approved_at,
        o.order_delivered_carrier_date,
        o.order_delivered_customer_date,
        o.order_estimated_delivery_date::date,
        r.worst_review_score
    FROM raw_orders o
    JOIN raw_customers c ON c.customer_id = o.customer_id
    LEFT JOIN (
        SELECT order_id, min(review_score) AS worst_review_score
        FROM raw_order_reviews
        GROUP BY order_id
    ) r ON r.order_id = o.order_id
"""

ORDER_SELLERS_SQL = """
    INSERT INTO order_sellers (order_id, seller_id)
    SELECT DISTINCT i.order_id, i.seller_id
    FROM raw_order_items i
    JOIN orders o ON o.order_id = i.order_id
"""

DERIVED_TABLES = ("orders", "order_sellers")


async def build_all(dsn: str) -> dict[str, int]:
    asyncpg_dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(asyncpg_dsn)
    try:
        async with conn.transaction():
            # Khoá ngoại buộc xoá cả hai bảng trong cùng một câu lệnh; xoá riêng bảng
            # cha sẽ bị từ chối. Không dùng CASCADE — nó sẽ lan sang bảng khác nếu
            # sau này có bảng trỏ tới. Thứ tự INSERT thì ngược lại: orders phải có
            # trước order_sellers.
            await conn.execute("TRUNCATE TABLE order_sellers, orders")
            await conn.execute(ORDERS_SQL)
            await conn.execute(ORDER_SELLERS_SQL)

        return {
            table: await conn.fetchval(f'SELECT count(*) FROM "{table}"')
            for table in DERIVED_TABLES
        }
    finally:
        await conn.close()


def main() -> None:
    counts = asyncio.run(build_all(settings.DATABASE_URL))
    for table, count in counts.items():
        print(f"{table}: {count} rows")


if __name__ == "__main__":
    main()
