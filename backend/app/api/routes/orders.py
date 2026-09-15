from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import SessionDep, get_current_user
from app.services.orders import (
    PAGE_SIZE,
    DeliveryOutcome,
    OrderDetail,
    OrderFilters,
    OrderList,
    OrderSort,
    OrderStatus,
    SortDirection,
    export_orders_csv,
    get_order_detail,
    list_customer_states,
    list_orders,
)

router = APIRouter(tags=["orders"], dependencies=[Depends(get_current_user)])

# OFFSET của Postgres là bigint; trang lớn hơn mức này tràn số và thành lỗi 500 thay vì
# một trang rỗng.
MAX_PAGE = (2**63 - 1) // PAGE_SIZE


def _day_range(
    name: str, start: date | None, end: date | None
) -> tuple[date, date] | None:
    # Cùng luật với start_date/end_date của /dashboard: một đầu thì không phải một khoảng.
    if (start is None) != (end is None):
        raise HTTPException(
            status_code=422,
            detail=f"{name}_from and {name}_to must be given together, or both omitted",
        )
    return None if start is None or end is None else (start, end)


class OrderQuery(BaseModel):
    filters: OrderFilters
    sort: OrderSort
    direction: SortDirection


# Bộ tham số lọc và sắp xếp của mọi endpoint đọc danh sách đơn. Khai một chỗ để các
# endpoint đó không bao giờ lệch nhau về tên, giá trị mặc định hay luật khoảng ngày.
# Mặc định đơn mới đặt nhất lên đầu: Purchase Date là mốc mọi đơn đều có.
def order_query(
    order_id: str = "",
    order_status: OrderStatus | None = None,
    delivery_outcome: DeliveryOutcome | None = None,
    purchased_from: date | None = None,
    purchased_to: date | None = None,
    delivered_from: date | None = None,
    delivered_to: date | None = None,
    # customer_state chứ không phải state, cùng lý do với /dashboard: đây là bang khách
    # nhận hàng, không phải bang người bán.
    customer_state: str | None = None,
    seller_id: str | None = None,
    sort: OrderSort = "purchased_at",
    direction: SortDirection = "desc",
) -> OrderQuery:
    return OrderQuery(
        filters=OrderFilters(
            order_id_prefix=order_id,
            order_status=order_status,
            delivery_outcome=delivery_outcome,
            purchased=_day_range("purchased", purchased_from, purchased_to),
            delivered=_day_range("delivered", delivered_from, delivered_to),
            customer_state=customer_state,
            seller_id=seller_id,
        ),
        sort=sort,
        direction=direction,
    )


OrderQueryDep = Annotated[OrderQuery, Depends(order_query)]


@router.get("/orders", response_model=OrderList)
async def orders(
    session: SessionDep,
    query: OrderQueryDep,
    page: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 1,
) -> OrderList:
    return await list_orders(
        session, query.filters, sort=query.sort, direction=query.direction, page=page
    )


# Phải khai báo trước /orders/{order_id}, không thì "export" bị hiểu là một mã đơn và
# nhận 404. Không có page: file gồm mọi đơn khớp bộ lọc, không chỉ trang đang xem.
# Content-Disposition dành cho ai gọi thẳng; CORS không mở header này cho trình duyệt,
# nên frontend tự đặt tên file.
@router.get("/orders/export")
async def export_orders(session: SessionDep, query: OrderQueryDep) -> StreamingResponse:
    return StreamingResponse(
        export_orders_csv(
            session, query.filters, sort=query.sort, direction=query.direction
        ),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="orders.csv"'},
    )


@router.get("/orders/{order_id}", response_model=OrderDetail)
async def order_detail(session: SessionDep, order_id: str) -> OrderDetail:
    detail = await get_order_detail(session, order_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return detail


# Tuỳ chọn cho ô chọn bang của trang đơn hàng. Tách khỏi /orders vì danh sách này không
# đổi theo trang hay bộ lọc, nên chỉ cần gọi một lần khi mở trang. Đường dẫn không nằm
# dưới /orders: mẫu chặn `${BACKEND_URL}/orders**` của Playwright vượt cả dấu gạch chéo.
@router.get("/customer-states", response_model=list[str])
async def customer_states(session: SessionDep) -> list[str]:
    return await list_customer_states(session)
