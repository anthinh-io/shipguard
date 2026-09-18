from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import CurrentUserDep, PredictorDep, SessionDep, get_current_user
from app.services.order_lifecycle import (
    CanceledOrder,
    EditMilestoneTimestamp,
    InvalidMilestoneTimestampError,
    LifecycleConflictError,
    MilestoneRecorded,
    OrderNotFoundError,
    RecordMilestone,
    cancel_order,
    edit_milestone,
    record_milestone,
)
from app.services.order_milestones import Milestone
from app.services.order_notes import (
    NewOrderNote,
    OrderNote,
    add_order_note,
    list_order_notes,
)
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
from app.services.risk_assessments import (
    AssessmentNotFoundError,
    CreatedOrder,
    InterventionConflictError,
    InvalidOrderError,
    NewIntervention,
    NewOrder,
    ProductCategory,
    RiskAssessmentOut,
    SellerZipMissingError,
    create_new_order,
    list_product_categories,
    list_risk_assessments,
    record_intervention,
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


# Đơn + dòng sản phẩm + dòng thanh toán + Risk Assessment đầu tiên trong một giao dịch
# (ADR-0009) — đơn không bao giờ được tồn tại mà thiếu đánh giá (CONTEXT.md, mục Risk
# Assessment). InvalidOrderError giữ được vị trí trường sai, cùng khuôn detail mà
# Pydantic tự sinh cho lỗi 422 thường, để #32 chỉ đúng ô sai chứ không gom một dòng.
@router.post("/orders", response_model=CreatedOrder, status_code=201)
async def create_order(
    payload: NewOrder,
    session: SessionDep,
    predictor: PredictorDep,
    current_user: CurrentUserDep,
) -> CreatedOrder:
    try:
        return await create_new_order(session, predictor, current_user.user_id, payload)
    except InvalidOrderError as error:
        raise HTTPException(
            status_code=422,
            detail=[
                {"type": "value_error", "loc": ["body", *field_error.loc], "msg": field_error.msg}
                for field_error in error.errors
            ],
        ) from None
    except SellerZipMissingError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None


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


# Internal Note chỉ thêm được: không có PATCH hay DELETE, ghi nhầm thì thêm ghi chú đính
# chính. Mọi vai trò đã đăng nhập đều đọc và thêm được.
@router.get("/orders/{order_id}/notes", response_model=list[OrderNote])
async def order_notes(session: SessionDep, order_id: str) -> list[OrderNote]:
    notes = await list_order_notes(session, order_id)
    if notes is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return notes


@router.post("/orders/{order_id}/notes", response_model=OrderNote, status_code=201)
async def add_note(
    session: SessionDep,
    order_id: str,
    payload: NewOrderNote,
    current_user: CurrentUserDep,
) -> OrderNote:
    note = await add_order_note(session, order_id, current_user.user_id, payload.body)
    if note is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return note


# Mới nhất trên cùng. Đơn Olist lịch sử không bao giờ có Risk Assessment nên trả mảng
# rỗng, không phải 404 — 404 chỉ dành cho mã đơn không tồn tại.
@router.get("/orders/{order_id}/risk-assessments", response_model=list[RiskAssessmentOut])
async def order_risk_assessments(session: SessionDep, order_id: str) -> list[RiskAssessmentOut]:
    history = await list_risk_assessments(session, order_id)
    if history is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return history


# Ghi nhận một Order Milestone, và — trừ delivered_to_customer — sinh một Risk Assessment
# mới ở Prediction Checkpoint tương ứng (#33). delivered_to_customer chạy Reconciliation
# thay vào đó, nên PredictorDep vẫn khai trên route này để chặn ở tầng dependency-injection
# TRƯỚC khi transaction mở — dù bước ghi nhận giao hàng không thật sự cần predict.
@router.post("/orders/{order_id}/milestones", response_model=MilestoneRecorded, status_code=201)
async def record_order_milestone(
    order_id: str,
    payload: RecordMilestone,
    session: SessionDep,
    predictor: PredictorDep,
    current_user: CurrentUserDep,
) -> MilestoneRecorded:
    try:
        return await record_milestone(
            session, predictor, order_id, payload, current_user.user_id
        )
    except OrderNotFoundError:
        raise HTTPException(status_code=404, detail="Order not found") from None
    except LifecycleConflictError as error:
        raise HTTPException(
            status_code=409, detail={"code": error.code, "message": error.message}
        ) from None
    except InvalidMilestoneTimestampError as error:
        raise HTTPException(
            status_code=422,
            detail=[{"type": "value_error", "loc": ["body", "recorded_at"], "msg": error.msg}],
        ) from None
    except SellerZipMissingError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None


# Sửa mốc mới nhất — {milestone} ghi rõ tên trên path, không alias ngầm "latest": người
# gọi nhắm nhầm mốc nhận đúng lỗi NotLatestMilestoneError thay vì sửa nhầm mốc khác.
@router.patch("/orders/{order_id}/milestones/{milestone}", response_model=MilestoneRecorded)
async def edit_order_milestone(
    order_id: str,
    milestone: Milestone,
    payload: EditMilestoneTimestamp,
    session: SessionDep,
    predictor: PredictorDep,
    current_user: CurrentUserDep,
) -> MilestoneRecorded:
    try:
        return await edit_milestone(
            session, predictor, order_id, milestone, payload, current_user.user_id
        )
    except OrderNotFoundError:
        raise HTTPException(status_code=404, detail="Order not found") from None
    except LifecycleConflictError as error:
        raise HTTPException(
            status_code=409, detail={"code": error.code, "message": error.message}
        ) from None
    except InvalidMilestoneTimestampError as error:
        raise HTTPException(
            status_code=422,
            detail=[{"type": "value_error", "loc": ["body", "recorded_at"], "msg": error.msg}],
        ) from None
    except SellerZipMissingError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None


# Không PredictorDep: hủy đơn không sinh Risk Assessment, không chạy Reconciliation.
@router.post("/orders/{order_id}/cancellation", response_model=CanceledOrder, status_code=201)
async def cancel_order_route(order_id: str, session: SessionDep) -> CanceledOrder:
    try:
        return await cancel_order(session, order_id)
    except OrderNotFoundError:
        raise HTTPException(status_code=404, detail="Order not found") from None
    except LifecycleConflictError as error:
        raise HTTPException(
            status_code=409, detail={"code": error.code, "message": error.message}
        ) from None


# Tuỳ chọn cho ô chọn bang của trang đơn hàng. Tách khỏi /orders vì danh sách này không
# đổi theo trang hay bộ lọc, nên chỉ cần gọi một lần khi mở trang. Đường dẫn không nằm
# dưới /orders: mẫu chặn `${BACKEND_URL}/orders**` của Playwright vượt cả dấu gạch chéo.
@router.get("/customer-states", response_model=list[str])
async def customer_states(session: SessionDep) -> list[str]:
    return await list_customer_states(session)


# Danh mục sản phẩm kèm nhãn hiển thị, cho ô chọn của biểu mẫu tạo đơn. Cùng lý do với
# /customer-states: cấp gốc, không nằm dưới /orders.
@router.get("/product-categories", response_model=list[ProductCategory])
async def product_categories(session: SessionDep) -> list[ProductCategory]:
    return await list_product_categories(session)


# Ghi nhận Intervention cho một Risk Assessment High Risk — #35. Cấp gốc theo mã lần đánh
# giá, không nằm dưới /orders: cùng lý do với /customer-states, /product-categories.
@router.post(
    "/risk-assessments/{assessment_id}/intervention",
    response_model=RiskAssessmentOut,
    status_code=201,
)
async def record_assessment_intervention(
    assessment_id: int,
    payload: NewIntervention,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> RiskAssessmentOut:
    try:
        return await record_intervention(session, assessment_id, payload, current_user.user_id)
    except AssessmentNotFoundError:
        raise HTTPException(status_code=404, detail="Risk assessment not found") from None
    except InterventionConflictError as error:
        raise HTTPException(
            status_code=409, detail={"code": error.code, "message": error.message}
        ) from None
