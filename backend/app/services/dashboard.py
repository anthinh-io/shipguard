from datetime import date, datetime, time, timedelta
from typing import Literal

import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.derived import order_sellers, orders, sellers

# Bộ Olist thực chất kết thúc tháng 8/2018: tháng 9 chỉ còn 56 đơn giao, tháng 10 chỉ
# còn 3. Không có ngưỡng thì kỳ mặc định kéo tới tận những tháng đó, tỷ lệ dựng trên
# mẫu vài đơn và màn hình trông như hệ thống hỏng chứ không phải như dữ liệu đã hết.
FULL_MONTH_MIN_DELIVERED_ORDERS = 100
DEFAULT_PERIOD_MONTHS = 12

Granularity = Literal["day", "week", "month"]

# Comparison Period theo CONTEXT.md: kỳ liền trước có cùng độ dài, hoặc cùng kỳ của năm
# trước. "none" là chế độ thứ ba trên thanh bộ lọc, không phải sự vắng mặt của tham số.
ComparisonMode = Literal["none", "previous", "year_over_year"]

# Hai ngưỡng đều tính bằng ngày, cùng một kiểu số học, nên test ranh giới chỉ là hai
# con số cố định. 183 ngày là "6 tháng" quy về ngày; dùng số học lịch thay cho nó sẽ
# làm ngưỡng trượt theo từng tháng và kéo thêm một phụ thuộc chỉ để phục vụ một phép so.
DAILY_MAX_SPAN_DAYS = 31  # "dưới 31 ngày" → kỳ 30 ngày gom theo ngày
WEEKLY_MAX_SPAN_DAYS = 183  # "dưới 6 tháng" → kỳ 182 ngày gom theo tuần

# Small Sample theo CONTEXT.md: dưới 30 đơn sau khi lọc. Đúng 30 đơn KHÔNG bị gắn cờ.
SMALL_SAMPLE_MAX_ORDERS = 30

# Delivered Order theo CONTEXT.md: đơn đã tới tay khách và có ngày giao thực tế. Đây là
# tập đơn duy nhất được tính vào KPI — bảng dẫn xuất cố ý giữ mọi đơn kèm cột trạng
# thái, việc lọc thuộc về truy vấn KPI. Dựng bằng Core chứ không phải chuỗi SQL để các
# truy vấn sau còn ghép thêm điều kiện lọc và mệnh đề gom nhóm lên trên.
DELIVERED = sa.and_(
    orders.c.order_status == "delivered",
    orders.c.delivered_to_customer_at.is_not(None),
)


class ReportingPeriod(BaseModel):
    start_date: date
    end_date: date


class TrendPoint(BaseModel):
    bucket_start: date
    delivered_orders: int
    late_orders: int
    # None nghĩa là nhóm rỗng — không có đơn nào giao trong khoảng đó — chứ không phải
    # 0%. "Không có đơn nào" và "không đơn nào trễ" là hai điều khác nhau.
    late_rate: float | None


class LateRateTrend(BaseModel):
    granularity: Granularity
    points: list[TrendPoint]


class StateLateRate(BaseModel):
    # Region theo CONTEXT.md: bang của khách hàng NHẬN hàng, không phải bang người bán
    # gửi đi. orders.customer_state đã là đúng cột này.
    customer_state: str
    delivered_orders: int
    late_orders: int
    late_rate: float


class StageDuration(BaseModel):
    median_days: float | None
    p90_days: float | None


class DashboardKpis(BaseModel):
    delivered_orders: int
    late_orders: int
    on_time_rate: float | None
    payment_approval: StageDuration
    seller_handling: StageDuration
    carrier_transit: StageDuration
    late_related_low_review_rate: float | None


class SellerOption(BaseModel):
    seller_id: str
    # Seller State theo CONTEXT.md: bang người bán GỬI hàng đi, chỉ để nhận diện người
    # bán. Không nhầm với customer_state của StateLateRate, vốn là bang khách nhận.
    seller_city: str
    seller_state: str
    delivered_orders: int


class DashboardFilters(BaseModel):
    # None ở mỗi trường nghĩa là không lọc theo chiều đó, không phải "lọc theo giá trị
    # mặc định". period=None cũng là đường vào bộ số vàng: test đối chiếu trên toàn bộ
    # dữ liệu không qua kỳ báo cáo nào.
    period: ReportingPeriod | None = None
    customer_state: str | None = None
    seller_id: str | None = None


def _where(filters: DashboardFilters) -> list[sa.ColumnElement[bool]]:
    clauses: list[sa.ColumnElement[bool]] = [DELIVERED]
    if filters.period is not None:
        clauses.append(_delivered_within(filters.period))
    if filters.customer_state is not None:
        clauses.append(orders.c.customer_state == filters.customer_state)
    if filters.seller_id is not None:
        # EXISTS chứ không phải JOIN, và lý do là cú pháp chứ không phải hiệu năng:
        # danh sách này còn bị nối vào mệnh đề ON của LEFT JOIN trong
        # compute_late_rate_trend, nơi vế trái là generate_series và không có chỗ nào
        # đặt thêm một bảng vào FROM. Tiện thể nó cũng giữ đúng một dòng mỗi đơn.
        #
        # Đơn ghép nhiều người bán vì vậy thuộc về MỌI người bán tham gia — đúng
        # CONTEXT.md mục Multi-Seller Order, và là nguồn của sai lệch ~1,3% đã chấp
        # nhận trong #1. Đừng khử.
        clauses.append(
            sa.exists().where(
                sa.and_(
                    order_sellers.c.order_id == orders.c.order_id,
                    order_sellers.c.seller_id == filters.seller_id,
                )
            )
        )
    return clauses


def is_small_sample(delivered_orders: int) -> bool:
    """Tập đơn sau khi lọc có đủ nhỏ để mọi tỷ lệ phần trăm mất ý nghĩa hay không.

    Chỉ gắn cờ, không ẩn số liệu — người dùng vẫn có quyền xem, chỉ cần biết là đừng
    kết luận chắc từ đó.
    """
    return delivered_orders < SMALL_SAMPLE_MAX_ORDERS


async def resolve_default_period(session: AsyncSession) -> ReportingPeriod | None:
    """Kỳ mặc định: 12 tháng gần nhất tính đến tháng đầy đủ cuối cùng.

    Không tháng nào đạt ngưỡng thì lùi về tháng cuối cùng có đơn đã giao. Trả None chỉ
    khi không có đơn đã giao nào — lúc đó không có kỳ nào suy ra được từ dữ liệu.
    """
    month = sa.func.date_trunc("month", orders.c.delivered_to_customer_at)
    monthly = (
        sa.select(month.label("month"), sa.func.count().label("delivered"))
        .where(DELIVERED)
        .group_by(month)
        .cte("monthly")
    )
    # FILTER không áp được lên aggregate của một aggregate ở cùng một tầng, nên phải
    # qua CTE. coalesce gộp luôn nhánh dự phòng vào đây để không tốn lượt đi về thứ hai.
    chosen = sa.select(
        sa.func.coalesce(
            sa.func.max(monthly.c.month).filter(
                monthly.c.delivered >= FULL_MONTH_MIN_DELIVERED_ORDERS
            ),
            sa.func.max(monthly.c.month),
        ).label("end_month")
    ).cte("chosen")
    first_of_end_month = sa.cast(chosen.c.end_month, sa.Date)
    row = (
        await session.execute(
            sa.select(
                sa.cast(
                    chosen.c.end_month
                    - sa.func.make_interval(0, DEFAULT_PERIOD_MONTHS - 1),
                    sa.Date,
                ).label("start_date"),
                (
                    sa.cast(
                        chosen.c.end_month + sa.func.make_interval(0, 1), sa.Date
                    )
                    - 1
                ).label("end_date"),
            ).where(first_of_end_month.is_not(None))
        )
    ).one_or_none()
    if row is None:
        return None
    return ReportingPeriod(start_date=row.start_date, end_date=row.end_date)


def _stage_percentiles(
    column: sa.ColumnElement,
) -> tuple[sa.ColumnElement, sa.ColumnElement]:
    # Cột chặng là INTERVAL; percentile_cont cần một biểu thức số. epoch/86400 quy đổi
    # sang số ngày dạng float. percentile_cont tự bỏ qua NULL, nên các đơn thiếu mốc
    # trung gian (chưa bàn giao cho vận chuyển, v.v.) không kéo lệch kết quả — mẫu số
    # của một chặng vốn khác mẫu số đơn đã giao, và đó là đúng.
    #
    # Trung vị và phân vị 90, không dùng trung bình cộng: cả ba chặng lệch đuôi mạnh,
    # một nhúm đơn cá biệt kéo trung bình lệch xa giá trị điển hình (xem CONTEXT.md).
    days = sa.extract("epoch", column) / 86400.0
    return (
        sa.func.percentile_cont(0.5).within_group(days),
        sa.func.percentile_cont(0.9).within_group(days),
    )


async def compute_kpis(session: AsyncSession, filters: DashboardFilters) -> DashboardKpis:
    """Tỷ lệ giao đúng hạn, số đơn trễ, ba chặng thời gian và tỷ lệ đánh giá thấp do
    trễ — tất cả trên tập đơn đã giao khớp `filters`.

    `filters.period` là None nghĩa là không lọc kỳ nào. Hai đường dẫn tới đó: test đối
    chiếu bộ số vàng trên toàn bộ dữ liệu, và trường hợp `resolve_default_period` không
    suy ra được kỳ nào vì chưa có đơn đã giao.

    Hàm này không tự giải kỳ mặc định; việc đó thuộc về route, để bên gọi còn hỏi được
    con số trên toàn bộ dữ liệu.
    """
    payment_approval_med, payment_approval_p90 = _stage_percentiles(
        orders.c.payment_approval
    )
    seller_handling_med, seller_handling_p90 = _stage_percentiles(
        orders.c.seller_handling
    )
    carrier_transit_med, carrier_transit_p90 = _stage_percentiles(
        orders.c.carrier_transit
    )
    # Mẫu số là đơn bị chấm 1–2 sao, tử số là số đơn trong đó bị giao trễ. Ba sao là
    # trung tính nên bị loại khỏi cả hai vế; đơn không có đánh giá nào cũng bị loại vì
    # so sánh với NULL không bao giờ đúng. Chiều ngược lại (đơn trễ / có đánh giá thấp)
    # trả lời một câu hỏi khác — xem CONTEXT.md mục Late-Related Low Review Rate.
    low_review = orders.c.worst_review_score <= 2
    low_reviews = sa.func.count().filter(low_review)
    low_and_late = sa.func.count().filter(
        sa.and_(low_review, orders.c.is_late.is_(True))
    )

    statement = sa.select(
        sa.func.count(),
        # is_late là NULL với đơn chưa giao, nên WHERE is_late lẫn WHERE NOT is_late
        # đều lặng lẽ bỏ chúng. Vị ngữ DELIVERED đã loại hết nhóm đó rồi, IS TRUE ở đây
        # là để nói rõ ý định.
        sa.func.count().filter(orders.c.is_late.is_(True)),
        payment_approval_med,
        payment_approval_p90,
        seller_handling_med,
        seller_handling_p90,
        carrier_transit_med,
        carrier_transit_p90,
        low_reviews,
        low_and_late,
    ).where(sa.and_(*_where(filters)))

    row = (await session.execute(statement)).one()
    (
        delivered_orders,
        late_orders,
        pa_med,
        pa_p90,
        sh_med,
        sh_p90,
        ct_med,
        ct_p90,
        low_reviews_count,
        low_and_late_count,
    ) = row
    on_time_rate = (
        None
        if delivered_orders == 0
        else (delivered_orders - late_orders) / delivered_orders
    )
    late_related_low_review_rate = (
        None if low_reviews_count == 0 else low_and_late_count / low_reviews_count
    )
    return DashboardKpis(
        delivered_orders=delivered_orders,
        late_orders=late_orders,
        on_time_rate=on_time_rate,
        payment_approval=StageDuration(median_days=pa_med, p90_days=pa_p90),
        seller_handling=StageDuration(median_days=sh_med, p90_days=sh_p90),
        carrier_transit=StageDuration(median_days=ct_med, p90_days=ct_p90),
        late_related_low_review_rate=late_related_low_review_rate,
    )


def _delivered_within(period: ReportingPeriod) -> sa.ColumnElement[bool]:
    # Chặn bằng dấu thời gian thay vì ép delivered_to_customer_at::date, để chỉ mục
    # ix_orders_delivered_to_customer_at còn dùng được. Cận trên là nửa đêm đầu ngày kế
    # tiếp, nên kết quả trùng khít với phép so ở mức ngày lịch.
    return sa.and_(
        orders.c.delivered_to_customer_at >= datetime.combine(
            period.start_date, time.min
        ),
        orders.c.delivered_to_customer_at
        < datetime.combine(period.end_date + timedelta(days=1), time.min),
    )


def _minus_one_year(day: date) -> date:
    try:
        return day.replace(year=day.year - 1)
    except ValueError:
        # Chỉ có đúng một ngày ném lỗi ở đây: 29/2 của năm nhuận, vì năm trước đó không
        # có ngày ấy. Lùi về 28/2 thay vì để cả yêu cầu vỡ.
        return day.replace(year=day.year - 1, day=28)


def resolve_comparison_period(
    period: ReportingPeriod | None, mode: ComparisonMode
) -> ReportingPeriod | None:
    """Kỳ đem ra đối chiếu với kỳ báo cáo, theo chế độ người dùng chọn.

    Trả None khi không so sánh, hoặc khi chưa có kỳ chính nào để mà đối chiếu. Hàm
    thuần: không chạm cơ sở dữ liệu, nên kỳ đối chiếu rơi ra ngoài dải dữ liệu là
    chuyện bình thường — lúc đó truy vấn chỉ đơn giản không ra đơn nào.
    """
    if period is None or mode == "none":
        return None
    if mode == "previous":
        # Cùng độ dài, kết thúc đúng ngày trước ngày bắt đầu của kỳ chính.
        span = period.end_date - period.start_date
        end_date = period.start_date - timedelta(days=1)
        return ReportingPeriod(start_date=end_date - span, end_date=end_date)
    return ReportingPeriod(
        start_date=_minus_one_year(period.start_date),
        end_date=_minus_one_year(period.end_date),
    )


def choose_granularity(period: ReportingPeriod) -> Granularity:
    """Backend chọn độ mịn theo độ dài kỳ, không phải frontend.

    Dưới 31 ngày gom theo ngày, dưới 6 tháng (183 ngày) gom theo tuần, dài hơn gom theo
    tháng. Mục đích: người dùng không bao giờ nhìn vào một biểu đồ chỉ có một điểm,
    cũng không nhìn vào một biểu đồ dày đặc không đọc nổi.
    """
    span_days = (period.end_date - period.start_date).days + 1
    if span_days < DAILY_MAX_SPAN_DAYS:
        return "day"
    if span_days < WEEKLY_MAX_SPAN_DAYS:
        return "week"
    return "month"


async def compute_late_rate_trend(
    session: AsyncSession,
    filters: DashboardFilters,
    granularity: Granularity | None = None,
) -> LateRateTrend:
    """Xu hướng tỷ lệ trễ theo thời gian, gom nhóm theo độ mịn do backend chọn.

    `filters.period` là None chỉ xảy ra khi chưa có đơn đã giao nào — không có khung
    thời gian nào để lấp khoảng trống, nên trả về rỗng.

    `granularity` để bên gọi áp một độ mịn có sẵn thay vì tự suy ra. Đường dẫn duy nhất
    tới đó là chuỗi của kỳ đối chiếu: hai kỳ cùng chế độ "cùng kỳ năm trước" có thể lệch
    nhau đúng một ngày vì năm nhuận, và một ngày đó đủ đẩy chúng sang hai độ mịn khác
    nhau — hai đường như vậy không chồng lên nhau được. Để None thì tự chọn như cũ.
    """
    period = filters.period
    if period is None:
        return LateRateTrend(granularity="month", points=[])

    if granularity is None:
        granularity = choose_granularity(period)
    start_ts = datetime.combine(period.start_date, time.min)
    end_ts = datetime.combine(period.end_date, time.min)

    # Gom nhóm trần chỉ trả về những nhóm có đơn, nên một kỳ dài mà dữ liệu dồn vào một
    # góc sẽ tụt xuống còn vài điểm. generate_series dựng khung đủ mọi mốc trong kỳ,
    # rồi LEFT JOIN vào dữ liệu thật để nhóm rỗng vẫn có mặt với late_rate là None.
    buckets = (
        sa.func.generate_series(
            sa.func.date_trunc(granularity, start_ts),
            sa.func.date_trunc(granularity, end_ts),
            sa.text(f"interval '1 {granularity}'"),
        )
        .table_valued("bucket_start", name="buckets")
        # render_derived() là bắt buộc: generate_series trả về một cột vô danh mà
        # Postgres tự đặt tên là "generate_series", không phải "bucket_start". Thiếu
        # lời gọi này thì SQLAlchemy đặt bí danh cho bảng nhưng không đổi tên cột, và
        # truy vấn vỡ với "column buckets.bucket_start does not exist".
        .render_derived()
    )

    bucket_of = sa.func.date_trunc(granularity, orders.c.delivered_to_customer_at)
    # _where(filters) gồm DELIVERED, _delivered_within(period) và bộ lọc bang nếu có.
    # Tất cả phải nằm trong điều kiện JOIN chứ không phải WHERE: nhóm đầu tiên bị
    # date_trunc kéo lùi về đầu tuần/đầu tháng, nên không chặn ở đây thì đơn giao
    # trước ngày bắt đầu (hoặc thuộc bang khác) lọt vào nhóm đó.
    join_condition = sa.and_(bucket_of == buckets.c.bucket_start, *_where(filters))

    statement = (
        sa.select(
            buckets.c.bucket_start,
            # count(order_id) chứ không phải count(*): nhóm rỗng phải đếm ra 0, không
            # phải 1 — mọi hàng NULL bên phải của LEFT JOIN vẫn có mặt.
            sa.func.count(orders.c.order_id),
            sa.func.count(orders.c.order_id).filter(orders.c.is_late.is_(True)),
        )
        .select_from(buckets)
        .outerjoin(orders, join_condition)
        .group_by(buckets.c.bucket_start)
        .order_by(buckets.c.bucket_start)
    )

    rows = (await session.execute(statement)).all()
    points = [
        TrendPoint(
            bucket_start=bucket_start.date(),
            delivered_orders=delivered,
            late_orders=late,
            late_rate=None if delivered == 0 else late / delivered,
        )
        for bucket_start, delivered, late in rows
    ]
    return LateRateTrend(granularity=granularity, points=points)


async def compute_late_rate_by_state(
    session: AsyncSession, filters: DashboardFilters
) -> list[StateLateRate]:
    """Tỷ lệ trễ theo bang khách hàng nhận hàng, xếp từ cao xuống thấp.

    customer_state là NOT NULL trên bảng dẫn xuất nên mọi đơn đã giao đều có một bang,
    không có nhóm nào bị bỏ sót vì thiếu dữ liệu. Khi filters.customer_state đã chọn
    sẵn một bang, kết quả tự nhiên rút về đúng một dòng — route không cần nhánh riêng.
    """
    statement = (
        sa.select(
            orders.c.customer_state,
            sa.func.count(),
            sa.func.count().filter(orders.c.is_late.is_(True)),
        )
        .where(sa.and_(*_where(filters)))
        .group_by(orders.c.customer_state)
    )

    rows = (await session.execute(statement)).all()
    by_state = [
        StateLateRate(
            customer_state=customer_state,
            delivered_orders=delivered,
            late_orders=late,
            late_rate=late / delivered,
        )
        for customer_state, delivered, late in rows
    ]
    # Xếp giảm dần theo tỷ lệ trễ để trả lời thẳng câu hỏi "xử lý vùng nào trước"; hoà
    # thì theo mã bang để kết quả tất định giữa các lần gọi.
    by_state.sort(key=lambda state: (-state.late_rate, state.customer_state))
    return by_state


async def list_customer_states(session: AsyncSession) -> list[str]:
    """Danh sách bang có đơn đã giao, không áp bộ lọc nào.

    Cố ý không lọc theo period hay customer_state: đây là tuỳ chọn cho ô chọn bang,
    nên chọn một bang không được làm biến mất các lựa chọn còn lại trong danh sách.
    """
    rows = (
        await session.execute(
            sa.select(orders.c.customer_state)
            .where(DELIVERED)
            .distinct()
            .order_by(orders.c.customer_state)
        )
    ).all()
    return [row.customer_state for row in rows]


def _like_prefix(query: str) -> str:
    # seller_city nhận chuỗi tự do người dùng gõ vào, nên "%" và "_" phải thành ký tự
    # thường. Không thoát thì gõ đúng một dấu "%" sẽ khớp toàn bộ 3.095 người bán.
    # Dấu chéo ngược phải thoát trước, nếu không nó sẽ thoát nhầm hai lần sau đó.
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"{escaped}%"


async def search_sellers(
    session: AsyncSession, query: str, limit: int
) -> list[SellerOption]:
    """Gợi ý người bán cho ô gõ dần, khớp tiền tố trên mã, bang và thành phố.

    Bộ Olist không có tên người bán — chỉ có mã băm 32 ký tự — nên mỗi gợi ý phải kèm
    bang và số đơn thì người dùng mới phân biệt nổi các dòng trông giống hệt nhau.

    Cố ý không nhận `DashboardFilters`: cùng lý do với `list_customer_states`, đây là
    tuỳ chọn cho bộ lọc nên chọn một tuỳ chọn không được làm biến mất hay thu nhỏ các
    lựa chọn còn lại. Hệ quả cần biết: một gợi ý ghi 45 đơn vẫn có thể chạm ngưỡng mẫu
    nhỏ sau khi người dùng áp thêm khoảng thời gian hay bang.
    """
    # Chuỗi rỗng khớp mọi thứ, và đổ cả 3.095 dòng ra không phải là "gợi ý".
    if not query.strip():
        return []

    pattern = _like_prefix(query.strip())
    delivered_orders = sa.func.count().label("delivered_orders")
    statement = (
        sa.select(
            sellers.c.seller_id,
            sellers.c.seller_city,
            sellers.c.seller_state,
            delivered_orders,
        )
        .select_from(sellers)
        .join(order_sellers, order_sellers.c.seller_id == sellers.c.seller_id)
        .join(orders, orders.c.order_id == order_sellers.c.order_id)
        .where(
            sa.and_(
                DELIVERED,
                sa.or_(
                    sellers.c.seller_id.ilike(pattern, escape="\\"),
                    sellers.c.seller_state.ilike(pattern, escape="\\"),
                    sellers.c.seller_city.ilike(pattern, escape="\\"),
                ),
            )
        )
        .group_by(sellers.c.seller_id, sellers.c.seller_city, sellers.c.seller_state)
        # Xếp theo số đơn giảm dần là chủ ý, không phải theo độ khớp: gõ tên bang hay
        # thành phố thì người dùng muốn thấy đối tác lớn trước. Hoà thì theo mã để kết
        # quả tất định giữa các lần gọi.
        .order_by(delivered_orders.desc(), sellers.c.seller_id)
        .limit(limit)
    )

    rows = (await session.execute(statement)).all()
    return [
        SellerOption(
            seller_id=row.seller_id,
            seller_city=row.seller_city,
            seller_state=row.seller_state,
            delivered_orders=row.delivered_orders,
        )
        for row in rows
    ]
