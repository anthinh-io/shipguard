from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep, get_current_user
from app.services.orders import PAGE_SIZE, OrderList, OrderSort, SortDirection, list_orders

router = APIRouter(tags=["orders"], dependencies=[Depends(get_current_user)])

# OFFSET của Postgres là bigint; trang lớn hơn mức này tràn số và thành lỗi 500 thay vì
# một trang rỗng.
MAX_PAGE = (2**63 - 1) // PAGE_SIZE


# Mặc định đơn mới đặt nhất lên đầu: Purchase Date là mốc mọi đơn đều có.
@router.get("/orders", response_model=OrderList)
async def orders(
    session: SessionDep,
    order_id: str = "",
    sort: OrderSort = "purchased_at",
    direction: SortDirection = "desc",
    page: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 1,
) -> OrderList:
    return await list_orders(
        session, order_id_prefix=order_id, sort=sort, direction=direction, page=page
    )
