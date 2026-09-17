import secrets
from collections.abc import Iterable
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, Literal

import sqlalchemy as sa
from pydantic import BaseModel, Field, StringConstraints, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.derived import (
    order_items,
    order_payments,
    order_sellers,
    orders,
    product_categories,
    sellers,
)
from app.models.risk import risk_assessments
from app.risk.predictor import OrderInput, OrderLine, RiskPredictor, StageForecast
from app.services.orders import list_customer_states

# Đúng bốn hình thức có ý nghĩa của dữ liệu Olist — not_defined là rác ghi nhận, không
# phải một lựa chọn cho đơn mới.
PaymentType = Literal["credit_card", "boleto", "voucher", "debit_card"]


class NewOrderItem(BaseModel):
    seller_id: str
    product_category_name: str
    # Cân nặng để trống được: dữ liệu Olist cũng có dòng thiếu cân nặng, và mô-đun dự
    # đoán vốn đã xử lý việc này (build_seller_orders gộp bằng sum, nên đơn thiếu mọi
    # cân nặng được hiểu là đơn nặng 0 gram, không phải "chưa biết" — hành vi sẵn có,
    # không sửa ở ticket này).
    product_weight_g: Annotated[int, Field(ge=0)] | None = None
    price: Annotated[float, Field(ge=0)]
    freight_value: Annotated[float, Field(ge=0)]


class NewOrderPayment(BaseModel):
    payment_type: PaymentType
    payment_installments: Annotated[int, Field(ge=1)]
    payment_value: Annotated[float, Field(ge=0)]

    @model_validator(mode="after")
    def _installments_need_credit_card(self) -> "NewOrderPayment":
        if self.payment_installments > 1 and self.payment_type != "credit_card":
            raise ValueError(
                "payment_installments greater than 1 requires payment_type credit_card"
            )
        return self


class NewOrder(BaseModel):
    purchased_at: datetime
    estimated_delivery_date: date
    customer_state: str
    customer_city: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    # Không đối chiếu với bảng toạ độ mã bưu chính như seller_zip_code_prefix: hành vi
    # này có sẵn từ mô-đun dự đoán (#30) và áp dụng như nhau cho mọi đơn Olist lịch sử —
    # mã bưu chính không có toạ độ (raw_geolocation không phủ hết CEP) làm distance_km
    # thành NaN mà mô hình đã học cách chấp nhận. Khác seller_zip_code_prefix: đó là cột
    # mới toanh có thể rỗng ở MỌI dòng ngay sau migration nếu quên dựng lại lớp dẫn xuất
    # — một lỗ hổng vận hành, không phải đặc thù dữ liệu — nên mới cần chặn ở 503.
    customer_zip_code_prefix: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1)
    ]
    items: Annotated[list[NewOrderItem], Field(min_length=1)]
    payments: Annotated[list[NewOrderPayment], Field(min_length=1)]

    @model_validator(mode="after")
    def _purchased_at_is_a_real_moment(self) -> "NewOrder":
        # Giao diện gửi ISO có offset (#31 mô tả); thiếu offset thì so với "bây giờ" bên
        # dưới sẽ ném TypeError thay vì một lỗi 422 rõ ràng.
        if self.purchased_at.tzinfo is None:
            raise ValueError("purchased_at must include a UTC offset")
        if self.purchased_at > datetime.now(timezone.utc):
            raise ValueError("purchased_at cannot be in the future")
        return self

    @model_validator(mode="after")
    def _estimated_delivery_date_not_before_purchase(self) -> "NewOrder":
        # So theo ngày lịch UTC, không theo lịch riêng của múi giờ người gửi: mốc của
        # đơn — đặt hàng, cam kết — theo đúng quy ước UTC của dữ liệu Olist như phần còn
        # lại của trang chi tiết (#32 đã nêu). purchased_at lưu naive sau khi đổi về UTC
        # (xem create_new_order), nên "ngày đặt" của hệ thống luôn là ngày UTC.
        if self.purchased_at.tzinfo is None:
            return self
        purchased_date = self.purchased_at.astimezone(timezone.utc).date()
        if self.estimated_delivery_date < purchased_date:
            raise ValueError("estimated_delivery_date cannot be before purchased_at")
        return self


class OrderFieldError(BaseModel):
    # int cho chỉ số phần tử trong items/payments, str cho tên trường — cùng hình dạng
    # loc mà Pydantic tự sinh.
    loc: tuple[int | str, ...]
    msg: str


class InvalidOrderError(Exception):
    """422 giữ được vị trí trường sai, cùng khuôn `[{type, loc, msg}]` của Pydantic.

    Người bán, danh mục, bang không tồn tại là những điều Pydantic không tự kiểm được
    vì cần một truy vấn — nhưng biểu mẫu tạo đơn (#32) vẫn cần trỏ đúng ô sai như mọi
    lỗi khác, nên lỗi ở đây được dựng theo đúng hình dạng đó thay vì một chuỗi trần.
    """

    def __init__(self, errors: list[OrderFieldError]) -> None:
        self.errors = errors
        super().__init__("; ".join(error.msg for error in errors))


class SellerZipMissingError(RuntimeError):
    """503: lớp dẫn xuất chưa dựng lại sau khi thêm seller_zip_code_prefix.

    Thà báo to còn hơn để distance_km lặng lẽ thành NaN — xem migration
    0011_risk_assessments và SELLERS_SQL của build_derived_data.
    """

    def __init__(self, seller_id: str) -> None:
        super().__init__(
            f"Seller {seller_id} is missing a zip code prefix; rebuild the derived "
            "data (python -m app.scripts.build_derived_data) after this migration"
        )


class RiskCauseOut(BaseModel):
    stage: str
    seller_id: str | None
    median_days: float
    historical_median_days: float
    excess_days: float


class RiskAssessmentOut(BaseModel):
    id: int
    checkpoint: str
    assessed_at: datetime
    late_probability: float
    is_high_risk: bool
    threshold_used: float
    model_version: str
    risk_cause: RiskCauseOut
    # Reconciliation (#33): None cho tới khi đơn được ghi nhận đã giao.
    was_correct: bool | None
    # Handled (CONTEXT.md): chỉ True cho lần đánh giá mới nhất của một đơn còn High Risk
    # và chưa có Intervention — list_risk_assessments tính, insert_assessment luôn False
    # vì dòng vừa tạo luôn là mới nhất và chưa thể có Intervention.
    needs_handling: bool = False


class CreatedOrder(BaseModel):
    order_id: str
    risk_assessment: RiskAssessmentOut


class ProductCategory(BaseModel):
    name: str
    label: str


def _stage_columns(stages: tuple[StageForecast, ...]) -> dict[str, float]:
    """Trung vị dự kiến và trung vị lịch sử — chỉ của các chặng CHƯA xong tại mốc này.

    Chặng đã xong (actual_days không None) để cặp cột của nó trống (NULL), đúng CONTEXT.md
    mục Risk Cause: chỉ chặng chưa xảy ra mới có thể là nguyên nhân.
    """
    columns: dict[str, float] = {}
    for forecast in stages:
        if forecast.actual_days is not None:
            continue
        columns[f"{forecast.stage}_median_days"] = forecast.median_days
        columns[f"{forecast.stage}_historical_median_days"] = forecast.historical_median_days
    return columns


def _risk_cause(row: sa.Row) -> RiskCauseOut:
    stage = row.risk_cause_stage
    median = getattr(row, f"{stage}_median_days")
    historical = getattr(row, f"{stage}_historical_median_days")
    return RiskCauseOut(
        stage=stage,
        seller_id=row.risk_cause_seller_id,
        median_days=median,
        historical_median_days=historical,
        excess_days=median - historical,
    )


def _to_assessment(row: sa.Row, *, needs_handling: bool = False) -> RiskAssessmentOut:
    return RiskAssessmentOut(
        id=row.id,
        checkpoint=row.checkpoint,
        assessed_at=row.assessed_at,
        late_probability=row.late_probability,
        is_high_risk=row.is_high_risk,
        threshold_used=row.threshold_used,
        model_version=row.model_version,
        risk_cause=_risk_cause(row),
        was_correct=row.was_correct,
        needs_handling=needs_handling,
    )


async def _load_sellers(session: AsyncSession, seller_ids: set[str]) -> dict[str, sa.Row]:
    rows = (
        await session.execute(
            sa.select(
                sellers.c.seller_id, sellers.c.seller_state, sellers.c.seller_zip_code_prefix
            ).where(sellers.c.seller_id.in_(seller_ids))
        )
    ).all()
    return {row.seller_id: row for row in rows}


async def _load_known_categories(session: AsyncSession, names: set[str]) -> set[str]:
    return set(
        await session.scalars(
            sa.select(product_categories.c.product_category_name).where(
                product_categories.c.product_category_name.in_(names)
            )
        )
    )


def _reference_errors(
    payload: NewOrder,
    seller_by_id: dict[str, sa.Row],
    known_categories: set[str],
    valid_states: set[str],
) -> list[OrderFieldError]:
    errors: list[OrderFieldError] = []
    if payload.customer_state not in valid_states:
        errors.append(
            OrderFieldError(
                loc=("customer_state",),
                msg=(
                    f"customer_state must be one of the {len(valid_states)} states "
                    "that already have orders"
                ),
            )
        )
    for index, item in enumerate(payload.items):
        if item.seller_id not in seller_by_id:
            errors.append(
                OrderFieldError(
                    loc=("items", index, "seller_id"),
                    msg=f"Seller {item.seller_id} does not exist",
                )
            )
        if item.product_category_name not in known_categories:
            errors.append(
                OrderFieldError(
                    loc=("items", index, "product_category_name"),
                    msg=f"Category {item.product_category_name} does not exist",
                )
            )
    return errors


# Dùng chung bởi _build_order_input (đơn mới, đọc từ NewOrder) và
# order_lifecycle.load_order_input (đơn đã tồn tại, đọc từ sa.Row của order_items/
# order_payments) — cả hai nguồn đều có đúng các thuộc tính dưới đây dù kiểu khác nhau
# (Pydantic vs. Row), nên gõ kiểu lỏng thay vì ép cùng một type. Tách ra để luật gộp
# (_payment_summary trong risk/features.py) chỉ có một chỗ viết, không lệch nhau giữa lúc
# tạo đơn và lúc đánh giá lại theo mốc (#33).
def _build_lines_and_payments(
    items: Iterable[Any],
    payments: Iterable[Any],
    seller_by_id: dict[str, sa.Row],
) -> tuple[tuple[OrderLine, ...], tuple[str, ...], int]:
    lines = tuple(
        OrderLine(
            seller_id=item.seller_id,
            seller_state=seller_by_id[item.seller_id].seller_state,
            seller_zip=seller_by_id[item.seller_id].seller_zip_code_prefix,
            product_category_name=item.product_category_name,
            product_weight_g=item.product_weight_g,
            price=item.price,
            freight_value=item.freight_value,
        )
        for item in items
    )
    # Khớp cách lệnh huấn luyện gộp nhiều dòng thanh toán về một đơn (_payment_summary
    # trong risk/features.py): payment_type_combo là tập hình thức khác nhau đã sắp xếp,
    # max_installments là số kỳ lớn nhất. Lệch cách gộp này thì đặc trưng lệch âm thầm so
    # với lúc huấn luyện.
    payment_types = tuple(sorted({payment.payment_type for payment in payments}))
    max_installments = max(payment.payment_installments for payment in payments)
    return lines, payment_types, max_installments


def _build_order_input(
    order_id: str, payload: NewOrder, purchased_at: datetime, seller_by_id: dict[str, sa.Row]
) -> OrderInput:
    lines, payment_types, max_installments = _build_lines_and_payments(
        payload.items, payload.payments, seller_by_id
    )
    return OrderInput(
        order_id=order_id,
        purchased_at=purchased_at,
        estimated_delivery_date=payload.estimated_delivery_date,
        customer_state=payload.customer_state,
        customer_zip=payload.customer_zip_code_prefix,
        lines=lines,
        payment_types=payment_types,
        payment_installments=max_installments,
    )


async def create_new_order(
    session: AsyncSession,
    predictor: RiskPredictor,
    current_user_id: int,
    payload: NewOrder,
) -> CreatedOrder:
    """Tạo đơn cùng lần Risk Assessment đầu tiên trong một giao dịch (ADR-0009).

    Đơn không bao giờ được tồn tại mà thiếu đánh giá — CONTEXT.md, mục Risk Assessment —
    nên việc dự đoán và mọi câu ghi đều nằm trong cùng một khối, và commit chỉ chạy một
    lần ở cuối.
    """
    seller_ids = {item.seller_id for item in payload.items}
    category_names = {item.product_category_name for item in payload.items}

    seller_by_id = await _load_sellers(session, seller_ids)
    known_categories = await _load_known_categories(session, category_names)
    valid_states = set(await list_customer_states(session))

    errors = _reference_errors(payload, seller_by_id, known_categories, valid_states)
    if errors:
        raise InvalidOrderError(errors)

    # Chỉ kiểm mã bưu chính của người bán đã xác nhận tồn tại — một người bán chưa có
    # trong sellers không nên vừa nhận lỗi 422 (không tồn tại) vừa nhận 503 (thiếu zip).
    missing_zip = next(
        (
            seller_id
            for seller_id, row in seller_by_id.items()
            if row.seller_zip_code_prefix is None
        ),
        None,
    )
    if missing_zip is not None:
        raise SellerZipMissingError(missing_zip)

    order_id = secrets.token_hex(16)
    # Đổi về UTC rồi bỏ tzinfo: mọi mốc đơn lưu naive theo quy ước dữ liệu Olist (xem
    # app/models/derived.py). Bộ dự đoán cũng cần một datetime naive — trộn tz-aware và
    # tz-naive trong cùng phép trừ của deadline_days sẽ ném TypeError.
    purchased_at = payload.purchased_at.astimezone(timezone.utc).replace(tzinfo=None)

    order_input = _build_order_input(order_id, payload, purchased_at, seller_by_id)

    order_value = sum(
        (Decimal(str(item.price)) + Decimal(str(item.freight_value)) for item in payload.items),
        Decimal("0"),
    )

    await session.execute(
        sa.insert(orders).values(
            order_id=order_id,
            order_status="created",
            customer_state=payload.customer_state,
            customer_city=payload.customer_city,
            customer_zip_code_prefix=payload.customer_zip_code_prefix,
            purchased_at=purchased_at,
            estimated_delivery_date=payload.estimated_delivery_date,
            order_value=order_value,
        )
    )

    # Một câu INSERT nhiều dòng mỗi bảng thay vì một câu lệnh cho từng dòng: cùng kết
    # quả, một lượt round-trip thay vì một lượt cho mỗi sản phẩm/người bán/dòng thanh
    # toán.
    await session.execute(
        sa.insert(order_items),
        [
            {
                "order_id": order_id,
                "order_item_id": index,
                # Mỗi dòng sản phẩm sinh một mã sản phẩm ẩn danh mới — đơn tạo trong
                # Ship Guard không có sản phẩm Olist thật đứng sau nó.
                "product_id": secrets.token_hex(16),
                "product_category_name": item.product_category_name,
                "product_weight_g": item.product_weight_g,
                "price": Decimal(str(item.price)),
                "freight_value": Decimal(str(item.freight_value)),
                "seller_id": item.seller_id,
            }
            for index, item in enumerate(payload.items, start=1)
        ],
    )

    # dict.fromkeys giữ thứ tự xuất hiện đầu tiên trong khi loại trùng — một người bán
    # có nhiều dòng sản phẩm chỉ cần một dòng trong order_sellers.
    await session.execute(
        sa.insert(order_sellers),
        [
            {"order_id": order_id, "seller_id": seller_id}
            for seller_id in dict.fromkeys(item.seller_id for item in payload.items)
        ],
    )

    await session.execute(
        sa.insert(order_payments),
        [
            {
                "order_id": order_id,
                "payment_sequential": index,
                "payment_type": payment.payment_type,
                "payment_installments": payment.payment_installments,
                "payment_value": Decimal(str(payment.payment_value)),
            }
            for index, payment in enumerate(payload.payments, start=1)
        ],
    )

    assessment = await insert_assessment(
        session, predictor, order_id, order_input, current_user_id
    )

    await session.commit()

    return CreatedOrder(order_id=order_id, risk_assessment=assessment)


async def insert_assessment(
    session: AsyncSession,
    predictor: RiskPredictor,
    order_id: str,
    order_input: OrderInput,
    current_user_id: int,
) -> RiskAssessmentOut:
    """Predict rồi ghi một dòng `risk_assessments` — không tự commit.

    Người gọi kiểm soát ranh giới giao dịch (ADR-0009). Dùng chung bởi create_new_order
    (#31) và order_lifecycle.record_milestone/edit_milestone (#33).
    """
    prediction = predictor.predict(order_input)
    threshold = settings.RISK_THRESHOLD
    # RETURNING nguyên bảng thay vì chỉ id rồi SELECT lại: một lượt round-trip đủ lấy cả
    # assessed_at (server_default=now()) lẫn mọi cột khác _to_assessment/_risk_cause cần.
    row = (
        await session.execute(
            sa.insert(risk_assessments)
            .values(
                order_id=order_id,
                checkpoint=prediction.checkpoint,
                late_probability=prediction.late_probability,
                # Mức rủi ro chốt ngay lúc đánh giá — đạt ngưỡng dùng >=, khớp CONTEXT.md mục
                # High Risk và metrics_at của lệnh huấn luyện.
                is_high_risk=prediction.late_probability >= threshold,
                threshold_used=threshold,
                model_version=prediction.model_version,
                risk_cause_stage=prediction.risk_cause.stage,
                risk_cause_seller_id=prediction.risk_cause.seller_id,
                created_by=current_user_id,
                **_stage_columns(prediction.stages),
            )
            .returning(risk_assessments)
        )
    ).one()
    return _to_assessment(row)


async def list_risk_assessments(
    session: AsyncSession, order_id: str
) -> list[RiskAssessmentOut] | None:
    """Lịch sử đánh giá, mới nhất trên cùng; None nếu không có đơn nào mang mã đó."""
    # orders.order_status là NOT NULL, nên None ở đây CHÍNH LÀ phép kiểm đơn không tồn
    # tại — không cần một câu _order_exists riêng rồi lại truy vấn order_status lần hai.
    order_status = await session.scalar(
        sa.select(orders.c.order_status).where(orders.c.order_id == order_id)
    )
    if order_status is None:
        return None
    rows = (
        await session.execute(
            sa.select(risk_assessments)
            .where(risk_assessments.c.order_id == order_id)
            # id phá thế hoà khi hai lần đánh giá trùng thời điểm.
            .order_by(risk_assessments.c.assessed_at.desc(), risk_assessments.c.id.desc())
        )
    ).all()
    return [
        _to_assessment(
            row,
            # Handled (CONTEXT.md): chỉ lần đánh giá MỚI NHẤT của một đơn còn High Risk
            # và chưa có Intervention mới là việc cần xử lý; đơn đã hủy không còn việc
            # cần xử lý dù đánh giá cuối vẫn High Risk.
            needs_handling=(
                index == 0
                and order_status != "canceled"
                and row.is_high_risk
                and row.intervention is None
            ),
        )
        for index, row in enumerate(rows)
    ]


async def list_product_categories(session: AsyncSession) -> list[ProductCategory]:
    """Danh mục sản phẩm kèm nhãn hiển thị, cho ô chọn của biểu mẫu tạo đơn."""
    rows = await session.execute(
        sa.select(
            product_categories.c.product_category_name,
            product_categories.c.product_category_name_english,
        ).order_by(product_categories.c.product_category_name_english)
    )
    return [
        ProductCategory(name=row.product_category_name, label=row.product_category_name_english)
        for row in rows
    ]
