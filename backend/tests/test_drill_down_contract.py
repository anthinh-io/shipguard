from datetime import date, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token

# Hợp đồng của drill-down (#25): con số trên biểu đồ và danh sách đơn mở ra từ nó phải
# là cùng một tập đơn. Frontend chỉ chép nguyên khoảng backend trả về vào tham số của
# /orders, nên kiểm ở đây — hai endpoint thật, cùng cơ sở dữ liệu — là đủ để khẳng định.

pytestmark = pytest.mark.usefixtures("derived_data")

# Hai kỳ tuần không bắt đầu vào thứ Hai: nhóm rìa là chỗ lỗi lệch một ngày giấu mình,
# điểm giữa kỳ thì đúng kiểu gì cũng qua. Kỳ thứ hai có nhóm đầu và nhóm cuối chỉ một
# ngày. Thêm một kỳ ngày và kỳ mặc định (tháng, không truyền tham số).
MIDWEEK_WEEKLY = {"start_date": "2018-01-03", "end_date": "2018-03-15"}
PERIODS = [
    pytest.param(MIDWEEK_WEEKLY, "week", id="weekly-wed-to-thu"),
    pytest.param(
        {"start_date": "2018-03-04", "end_date": "2018-05-28"},
        "week",
        id="weekly-sun-to-mon",
    ),
    pytest.param(
        {"start_date": "2018-03-01", "end_date": "2018-03-20"}, "day", id="daily"
    ),
    pytest.param({}, "month", id="default-monthly"),
]

# Người bán có nhiều đơn trễ nhất trong kỳ tuần giữa tuần, cùng bang khách nhận của
# phần lớn số đơn đó — để biến thể có bộ lọc không rơi vào một tập rỗng.
TOP_LATE_SELLER_AND_STATE = text(
    "SELECT os.seller_id, o.customer_state FROM orders o "
    "JOIN order_sellers os ON os.order_id = o.order_id "
    "WHERE o.order_status = 'delivered' AND o.delivered_to_customer_at IS NOT NULL "
    "AND o.is_late AND o.delivered_to_customer_at::date BETWEEN :start AND :end "
    "GROUP BY os.seller_id, o.customer_state "
    "ORDER BY count(*) DESC, os.seller_id, o.customer_state LIMIT 1"
)


@pytest.fixture(autouse=True)
def signed_in(client: AsyncClient) -> None:
    token = create_access_token(1, "operations_staff", [])
    client.headers["Authorization"] = f"Bearer {token}"


async def get_json(client: AsyncClient, path: str, params: dict[str, str]) -> Any:
    response = await client.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def late_orders_total(
    client: AsyncClient, delivered_from: str, delivered_to: str, **filters: str
) -> int:
    # Đúng bộ tham số frontend dựng trong lateOrdersQuery.
    body = await get_json(
        client,
        "/orders",
        {
            "delivery_outcome": "late",
            "delivered_from": delivered_from,
            "delivered_to": delivered_to,
            **filters,
        },
    )
    return body["total"]


async def assert_contract(
    client: AsyncClient, period: dict[str, str], granularity: str, **filters: str
) -> dict[str, Any]:
    dashboard = await get_json(client, "/dashboard", {**period, **filters})
    trend = dashboard["late_rate_trend"]
    assert trend["granularity"] == granularity

    for point in (trend["points"][0], trend["points"][-1]):
        total = await late_orders_total(
            client, point["bucket_from"], point["bucket_to"], **filters
        )
        assert total == point["late_orders"], point

    # Cột bang lấy khoảng từ reporting_period của phản hồi, không từ tham số gửi đi:
    # kỳ mặc định không có tham số nào.
    reporting_period = dashboard["reporting_period"]
    state = max(dashboard["late_rate_by_state"], key=lambda row: row["late_orders"])
    total = await late_orders_total(
        client,
        reporting_period["start_date"],
        reporting_period["end_date"],
        **{**filters, "customer_state": state["customer_state"]},
    )
    assert total == state["late_orders"] > 0, state
    return dashboard


@pytest.mark.parametrize(("period", "granularity"), PERIODS)
async def test_edge_trend_points_and_a_state_match_the_order_list(
    client: AsyncClient, period: dict[str, str], granularity: str
) -> None:
    dashboard = await assert_contract(client, period, granularity)

    points = dashboard["late_rate_trend"]["points"]
    if granularity != "week":
        # Không có đơn trễ nào ở hai điểm rìa thì 0 == 0 và bài test không chứng minh gì.
        assert points[0]["late_orders"] > 0
        assert points[-1]["late_orders"] > 0
        return
    # Tiền đề của hai kỳ tuần: nhóm rìa đủ bảy ngày, thứ Hai tới Chủ nhật, phải ra số
    # khác. Nếu trùng thì bài test vẫn xanh dù backend không kẹp. Chủ nhật 04/03/2018 có
    # 18 đơn giao nhưng không đơn nào trễ, nên ở đây không đòi late_orders > 0.
    for point in (points[0], points[-1]):
        monday = date.fromisoformat(point["bucket_start"])
        unclamped = await late_orders_total(
            client, monday.isoformat(), (monday + timedelta(days=6)).isoformat()
        )
        assert unclamped != point["late_orders"], point


async def test_seller_and_state_filters_carry_into_the_order_list(
    client: AsyncClient, session: AsyncSession
) -> None:
    seller_id, customer_state = (
        await session.execute(
            TOP_LATE_SELLER_AND_STATE,
            {
                "start": date.fromisoformat(MIDWEEK_WEEKLY["start_date"]),
                "end": date.fromisoformat(MIDWEEK_WEEKLY["end_date"]),
            },
        )
    ).one()

    dashboard = await assert_contract(
        client,
        MIDWEEK_WEEKLY,
        "week",
        seller_id=seller_id,
        customer_state=customer_state,
    )

    # Tập đã lọc vẫn có đơn trễ rải trong kỳ, nên khớp số ở trên không chỉ là 0 == 0.
    assert sum(p["late_orders"] for p in dashboard["late_rate_trend"]["points"]) > 0
