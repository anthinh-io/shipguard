import json
from datetime import date, timedelta
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.dashboard import (
    DEFAULT_PERIOD_MONTHS,
    FULL_MONTH_MIN_DELIVERED_ORDERS,
    SMALL_SAMPLE_MAX_ORDERS,
    DashboardFilters,
    ReportingPeriod,
    choose_granularity,
    compute_kpis,
    compute_late_rate_by_state,
    compute_late_rate_trend,
    is_small_sample,
    list_customer_states,
    resolve_comparison_period,
    resolve_default_period,
    search_sellers,
)

EDGE_CASE_ORDERS = json.loads(
    (Path(__file__).parent / "fixtures" / "edge_case_orders.json").read_text("utf-8")
)

EDGE_CASE_FILTERS = json.loads(
    (Path(__file__).parent / "fixtures" / "edge_case_filters.json").read_text("utf-8")
)

ORDER_IDS = bindparam("ids", type_=sa.ARRAY(sa.Text))

DELIVERED_MONTHS = (
    "SELECT date_trunc('month', delivered_to_customer_at) AS month, "
    "count(*) AS delivered FROM orders "
    "WHERE order_status = 'delivered' AND delivered_to_customer_at IS NOT NULL "
    "GROUP BY 1"
)


async def test_on_time_rate_over_unfiltered_data(session: AsyncSession) -> None:
    kpis = await compute_kpis(session, DashboardFilters())

    assert kpis.delivered_orders == 96470
    assert kpis.late_orders == 6534
    assert kpis.on_time_rate is not None
    assert round(kpis.on_time_rate * 100, 2) == 93.23


async def test_stage_durations_over_unfiltered_data(session: AsyncSession) -> None:
    kpis = await compute_kpis(session, DashboardFilters())

    # Bộ số vàng của #8, tính bằng ngày, làm tròn 2 chữ số. Trung vị và phân vị 90 —
    # không có trung bình cộng nào ở đây vì cả ba chặng lệch đuôi mạnh.
    assert round(kpis.payment_approval.median_days, 2) == 0.01
    assert round(kpis.payment_approval.p90_days, 2) == 1.44
    assert round(kpis.seller_handling.median_days, 2) == 1.82
    assert round(kpis.seller_handling.p90_days, 2) == 5.99
    assert round(kpis.carrier_transit.median_days, 2) == 7.10
    assert round(kpis.carrier_transit.p90_days, 2) == 18.90


async def test_late_related_low_review_rate_over_unfiltered_data(
    session: AsyncSession,
) -> None:
    kpis = await compute_kpis(session, DashboardFilters())

    assert kpis.late_related_low_review_rate is not None
    rate = round(kpis.late_related_low_review_rate * 100, 2)
    assert rate == 32.38
    # 62,47% là tỷ lệ tính ngược chiều: đơn trễ bị chấm 1–2 sao / đơn trễ có đánh giá.
    # Ra đúng con số này nghĩa là mẫu số và tử số đã bị đảo — xem CONTEXT.md mục
    # Late-Related Low Review Rate.
    assert rate != 62.47


async def test_three_star_orders_are_not_low_reviews(session: AsyncSession) -> None:
    # Gọi thẳng tầng dịch vụ — không chỉ đếm lại bằng SQL độc lập — để bài test này
    # thật sự ghim vào hành vi của compute_kpis. Nếu code coi 3 sao là đánh giá thấp,
    # rate_including_three_star sẽ khớp kpis.late_related_low_review_rate và bài test
    # không phân biệt được hai nhánh.
    three_star_count = await session.scalar(
        text(
            "SELECT count(*) FROM orders WHERE order_status = 'delivered' "
            "AND delivered_to_customer_at IS NOT NULL AND worst_review_score = 3"
        )
    )
    assert three_star_count > 0

    kpis = await compute_kpis(session, DashboardFilters())
    assert kpis.late_related_low_review_rate is not None

    low_and_late_including_three_star, low_including_three_star = (
        await session.execute(
            text(
                "SELECT count(*) FILTER (WHERE is_late), count(*) FROM orders "
                "WHERE order_status = 'delivered' "
                "AND delivered_to_customer_at IS NOT NULL AND worst_review_score <= 3"
            )
        )
    ).one()
    rate_including_three_star = (
        low_and_late_including_three_star / low_including_three_star
    )

    # Coi 3 sao là đánh giá thấp sẽ cho ra một tỷ lệ khác — nếu hai con số trùng nhau,
    # bài test này không phân biệt được gì cả.
    assert kpis.late_related_low_review_rate != rate_including_three_star
    assert round(kpis.late_related_low_review_rate * 100, 2) == 32.38


def test_granularity_switches_at_the_31_day_boundary() -> None:
    start = date(2018, 1, 1)

    # Kỳ 30 ngày (điểm cuối trong khoảng 29 ngày sau điểm đầu).
    thirty_days = ReportingPeriod(start_date=start, end_date=start + timedelta(days=29))
    # Kỳ 31 ngày — vượt ranh giới đúng một ngày.
    thirty_one_days = ReportingPeriod(
        start_date=start, end_date=start + timedelta(days=30)
    )

    assert choose_granularity(thirty_days) == "day"
    assert choose_granularity(thirty_one_days) == "week"


def test_granularity_switches_at_the_six_month_boundary() -> None:
    start = date(2018, 1, 1)

    # 182 ngày — "dưới 6 tháng" quy về ngày.
    span_182 = ReportingPeriod(start_date=start, end_date=start + timedelta(days=181))
    # 183 ngày — vượt ranh giới đúng một ngày.
    span_183 = ReportingPeriod(start_date=start, end_date=start + timedelta(days=182))

    assert choose_granularity(span_182) == "week"
    assert choose_granularity(span_183) == "month"


async def test_trend_fills_empty_buckets(session: AsyncSession) -> None:
    # Cuối dải dữ liệu Olist: chỉ 10/10 và 10/17 có đơn giao, sáu ngày ở giữa không có
    # đơn nào. Gom nhóm trần sẽ chỉ trả về hai điểm; lấp khoảng trống phải trả đủ 8.
    period = ReportingPeriod(start_date=date(2018, 10, 10), end_date=date(2018, 10, 17))

    trend = await compute_late_rate_trend(session, DashboardFilters(period=period))

    assert trend.granularity == "day"
    assert len(trend.points) == 8
    by_date = {point.bucket_start: point for point in trend.points}
    # Nhóm rỗng: không có đơn nào, và late_rate là None — không phải 0%.
    assert by_date[date(2018, 10, 12)].delivered_orders == 0
    assert by_date[date(2018, 10, 12)].late_rate is None
    # Hai ngày có đơn thật vẫn đếm đúng.
    assert by_date[date(2018, 10, 11)].delivered_orders == 1
    assert by_date[date(2018, 10, 17)].delivered_orders == 1


async def test_trend_over_unfiltered_default_period_has_no_gaps(
    session: AsyncSession,
) -> None:
    # Kỳ mặc định trùng khít mốc tháng nên không dính hiện tượng nhóm khuyết ở hai đầu;
    # 12 tháng phải cho ra đúng 12 điểm, không thiếu điểm nào.
    period = await resolve_default_period(session)
    assert period is not None

    trend = await compute_late_rate_trend(session, DashboardFilters(period=period))

    assert trend.granularity == "month"
    assert len(trend.points) == 12
    assert all(point.delivered_orders > 0 for point in trend.points)


async def test_state_distribution_uses_customer_state_not_seller_state(
    session: AsyncSession,
) -> None:
    # Đếm độc lập theo bang NGƯỜI BÁN, qua order_sellers -> raw_sellers. Hai tập phải
    # khác nhau, nếu không bài test này không phân biệt được gì cả — đây chính là cái
    # bẫy nêu trong CONTEXT.md mục Region.
    seller_state_sp_orders = await session.scalar(
        text(
            "SELECT count(*) FROM order_sellers os "
            "JOIN orders o ON o.order_id = os.order_id "
            "JOIN raw_sellers s ON s.seller_id = os.seller_id "
            "WHERE o.order_status = 'delivered' AND o.delivered_to_customer_at IS NOT NULL "
            "AND s.seller_state = 'SP'"
        )
    )

    by_state = {
        state.customer_state: state
        for state in await compute_late_rate_by_state(session, DashboardFilters())
    }

    assert seller_state_sp_orders != by_state["SP"].delivered_orders
    assert by_state["SP"].delivered_orders == 40494


async def test_state_distribution_covers_27_states(session: AsyncSession) -> None:
    by_state = await compute_late_rate_by_state(session, DashboardFilters())

    assert len(by_state) == 27
    rates = [state.late_rate for state in by_state]
    # Xếp giảm dần: bang trễ nhiều nhất đứng đầu, trả lời thẳng "xử lý vùng nào trước".
    assert rates == sorted(rates, reverse=True)


async def test_customer_state_filter_narrows_every_metric(
    session: AsyncSession,
) -> None:
    # Đếm lại độc lập bằng một truy vấn khoá cứng vào bang AL, rồi khẳng định
    # compute_kpis khớp đúng con số đó khi lọc theo customer_state="AL".
    expected_delivered = await session.scalar(
        text(
            "SELECT count(*) FROM orders WHERE order_status = 'delivered' "
            "AND delivered_to_customer_at IS NOT NULL AND customer_state = 'AL'"
        )
    )

    filters = DashboardFilters(customer_state="AL")
    kpis = await compute_kpis(session, filters)
    by_state = await compute_late_rate_by_state(session, filters)

    assert kpis.delivered_orders == expected_delivered
    # Lọc theo đúng một bang thì bảng phân bố tự nhiên rút về đúng một dòng.
    assert len(by_state) == 1
    assert by_state[0].customer_state == "AL"
    assert by_state[0].delivered_orders == expected_delivered


async def test_list_customer_states_ignores_filters(session: AsyncSession) -> None:
    # Danh sách tuỳ chọn không được lọc theo bất kỳ điều kiện nào — nếu không, chọn
    # một bang sẽ làm biến mất mọi lựa chọn khác trong ô chọn.
    states = await list_customer_states(session)

    assert len(states) == 27
    assert states == sorted(states)


async def test_default_period_ends_at_the_last_full_month(
    session: AsyncSession,
) -> None:
    # Tháng kết thúc tính lại từ dữ liệu bằng truy vấn riêng của bài test, để khẳng
    # định kỳ mặc định suy ra từ dữ liệu chứ không phải từ một ngày đóng cứng trong mã.
    expected_end_month = await session.scalar(
        text(f"SELECT max(month) FROM ({DELIVERED_MONTHS}) m WHERE delivered >= :n"),
        {"n": FULL_MONTH_MIN_DELIVERED_ORDERS},
    )

    period = await resolve_default_period(session)

    assert period is not None
    assert period.end_date.replace(day=1) == expected_end_month.date()
    # Trên bộ Olist, tháng đầy đủ cuối cùng là 8/2018: tháng 9 chỉ có 56 đơn giao.
    assert period.start_date == date(2017, 9, 1)
    assert period.end_date == date(2018, 8, 31)
    assert _months_spanned(period) == DEFAULT_PERIOD_MONTHS


async def test_default_period_falls_back_when_no_month_is_full(
    session: AsyncSession,
) -> None:
    every_id = sorted({o for group in EDGE_CASE_ORDERS.values() for o in group})
    try:
        # Thu bảng về tập con cố định ngay trong transaction rồi rollback ở finally.
        # Dịch vụ nhận đúng session này nên nó thấy thao tác xoá chưa commit. Khoá
        # ngoại quy định thứ tự: bảng nối trước, bảng cha sau.
        for table in ("order_sellers", "orders"):
            await session.execute(
                text(f"DELETE FROM {table} WHERE order_id <> ALL(:ids)").bindparams(
                    ORDER_IDS
                ),
                {"ids": every_id},
            )

        # Tiền đề của chính bài test. Thiếu khẳng định này, một lần sửa fixture sau
        # này đẩy một tháng vượt ngưỡng sẽ âm thầm lái test sang nhánh chính mà vẫn
        # xanh, và nhánh dự phòng mất phủ mà không ai biết.
        busiest_month = await session.scalar(
            text(f"SELECT max(delivered) FROM ({DELIVERED_MONTHS}) m")
        )
        assert 0 < busiest_month < FULL_MONTH_MIN_DELIVERED_ORDERS

        period = await resolve_default_period(session)

        assert period is not None
        # Không tháng nào đạt ngưỡng, nên lùi về tháng cuối cùng có đơn đã giao —
        # 9/2018, khác hẳn tháng kết thúc của nhánh chính.
        assert period.start_date == date(2017, 10, 1)
        assert period.end_date == date(2018, 9, 30)
        assert _months_spanned(period) == DEFAULT_PERIOD_MONTHS
    finally:
        await session.rollback()


async def test_seller_filter_narrows_every_metric(session: AsyncSession) -> None:
    seller_id = EDGE_CASE_FILTERS["busiest_seller"]
    # Đếm lại độc lập qua bảng nối, rồi khẳng định compute_kpis khớp đúng con số đó.
    expected_delivered = await session.scalar(
        text(
            "SELECT count(*) FROM orders o WHERE o.order_status = 'delivered' "
            "AND o.delivered_to_customer_at IS NOT NULL AND EXISTS ("
            "SELECT 1 FROM order_sellers os WHERE os.order_id = o.order_id "
            "AND os.seller_id = :seller_id)"
        ),
        {"seller_id": seller_id},
    )

    unfiltered = await compute_kpis(session, DashboardFilters())
    kpis = await compute_kpis(session, DashboardFilters(seller_id=seller_id))

    assert kpis.delivered_orders == expected_delivered
    # Nếu không hẹp hơn thì bộ lọc chưa hề được áp và bài test không phân biệt được gì.
    assert 0 < kpis.delivered_orders < unfiltered.delivered_orders


async def test_seller_filter_narrows_the_trend_and_the_state_distribution(
    session: AsyncSession,
) -> None:
    """Bộ lọc người bán phải áp cho cả ba khối, không riêng ô KPI.

    Đây là chỗ dễ hỏng nhất của cả tính năng: vị ngữ EXISTS được nối vào mệnh đề ON của
    LEFT JOIN trong compute_late_rate_trend, cạnh generate_series. Một EXISTS bị mất
    tương quan ở đó vẫn chạy, vẫn trả về kết quả, nhưng khớp mọi đơn — biểu đồ trông y
    hệt bản không lọc mà không có gì báo lỗi.
    """
    seller_id = EDGE_CASE_FILTERS["busiest_seller"]
    # Trải hết dải dữ liệu để không lẫn với kỳ mặc định.
    period = ReportingPeriod(start_date=date(2016, 1, 1), end_date=date(2018, 12, 31))
    filters = DashboardFilters(period=period, seller_id=seller_id)
    unfiltered = DashboardFilters(period=period)

    kpis = await compute_kpis(session, filters)
    trend = await compute_late_rate_trend(session, filters)
    unfiltered_trend = await compute_late_rate_trend(session, unfiltered)
    by_state = await compute_late_rate_by_state(session, filters)
    unfiltered_by_state = await compute_late_rate_by_state(session, unfiltered)

    trend_orders = sum(point.delivered_orders for point in trend.points)
    unfiltered_trend_orders = sum(
        point.delivered_orders for point in unfiltered_trend.points
    )

    # Khẳng định phân biệt: EXISTS mất tương quan sẽ làm hai con số này bằng nhau.
    assert trend_orders < unfiltered_trend_orders
    # Và biểu đồ phải đếm đúng cùng tập đơn với ô KPI, không phải một tập gần đúng.
    assert trend_orders == kpis.delivered_orders
    assert sum(point.late_orders for point in trend.points) == kpis.late_orders

    # Một người bán không giao tới đủ 27 bang, nên bảng phân bố phải ngắn lại.
    assert 0 < len(by_state) < len(unfiltered_by_state)
    assert sum(state.delivered_orders for state in by_state) == kpis.delivered_orders


async def test_seller_filter_combines_with_state_and_period(
    session: AsyncSession,
) -> None:
    seller_id = EDGE_CASE_FILTERS["busiest_seller"]
    period = ReportingPeriod(start_date=date(2018, 1, 1), end_date=date(2018, 6, 30))

    seller_only = await compute_kpis(session, DashboardFilters(seller_id=seller_id))
    combined = await compute_kpis(
        session,
        DashboardFilters(seller_id=seller_id, customer_state="SP", period=period),
    )

    # Ba chiều lọc chồng lên nhau, không cái nào ghi đè cái nào.
    assert 0 < combined.delivered_orders < seller_only.delivered_orders


async def test_multi_seller_order_counts_for_every_participating_seller(
    session: AsyncSession,
) -> None:
    # Một đơn ghép nhiều người bán thuộc về MỌI người bán tham gia (CONTEXT.md mục
    # Multi-Seller Order), nên lọc theo từng người bán đều phải thấy đúng đơn đó.
    order_id = EDGE_CASE_ORDERS["multi_seller"][0]
    seller_ids = [
        row.seller_id
        for row in (
            await session.execute(
                text("SELECT seller_id FROM order_sellers WHERE order_id = :order_id"),
                {"order_id": order_id},
            )
        ).all()
    ]

    assert len(seller_ids) > 1

    for seller_id in seller_ids:
        found = await session.scalar(
            text(
                "SELECT count(*) FROM orders o WHERE o.order_id = :order_id "
                "AND EXISTS (SELECT 1 FROM order_sellers os "
                "WHERE os.order_id = o.order_id AND os.seller_id = :seller_id)"
            ),
            {"order_id": order_id, "seller_id": seller_id},
        )
        assert found == 1


async def test_per_seller_totals_overshoot_the_overall_total(
    session: AsyncSession,
) -> None:
    """Sai lệch quy đơn theo người bán là quyết định đã chốt trong #1, không phải lỗi.

    Bài trên chứng minh *cách* quy đơn; bài này ghim *độ lớn*. Thiếu nó thì một lần
    "sửa cho hai con số khớp nhau" sau này sẽ đi qua mà không có gì đỏ.

    Con số ở đây là 1,4% chứ không phải 1,3% như văn xuôi của #1, và hai con số đo hai
    thứ khác nhau chứ không mâu thuẫn: 1,3% là 1.278 đơn nhiều người bán trên 96.470
    đơn, còn 1,4% là phần dôi ra của các cặp (đơn, người bán) — lớn hơn vì một số đơn
    có từ ba người bán trở lên nên đóng góp nhiều hơn một cặp thừa.
    """
    per_seller_sum = await session.scalar(
        text(
            "SELECT sum(n) FROM (SELECT count(*) AS n FROM order_sellers os "
            "JOIN orders o ON o.order_id = os.order_id "
            "WHERE o.order_status = 'delivered' "
            "AND o.delivered_to_customer_at IS NOT NULL GROUP BY os.seller_id) t"
        )
    )
    overall = (await compute_kpis(session, DashboardFilters())).delivered_orders

    assert overall == 96470
    assert per_seller_sum > overall
    # 1.278 đơn nhiều người bán (ghim ở test_build_derived_data) sinh ra ít nhất chừng
    # ấy cặp thừa; con số thực lớn hơn đúng bằng phần đơn có từ ba người bán trở lên.
    assert int(per_seller_sum) - overall == 1341
    # sum() của Postgres về đây là Decimal, không so bằng được với float.
    assert round((float(per_seller_sum) / overall - 1) * 100, 1) == 1.4


async def test_search_sellers_matches_id_prefix_state_and_city(
    session: AsyncSession,
) -> None:
    seller_id = EDGE_CASE_FILTERS["busiest_seller"]

    by_id = await search_sellers(session, seller_id[:8], limit=10)
    by_city = await search_sellers(session, "sao paulo", limit=10)
    by_state = await search_sellers(session, "SP", limit=10)

    assert [option.seller_id for option in by_id] == [seller_id]
    assert by_id[0].seller_city == "sao paulo"
    assert by_id[0].seller_state == "SP"
    assert by_id[0].delivered_orders > 0

    assert len(by_city) == 10
    assert all(option.seller_city == "sao paulo" for option in by_city)
    # Khớp bang là một nhánh khác hẳn khớp thành phố: SP có người bán ngoài sao paulo.
    assert all(option.seller_state == "SP" for option in by_state)
    assert {option.seller_id for option in by_state} != {
        option.seller_id for option in by_city
    }
    # Xếp theo số đơn giảm dần để đối tác lớn hiện trước.
    counts = [option.delivered_orders for option in by_state]
    assert counts == sorted(counts, reverse=True)


async def test_search_sellers_returns_nothing_for_an_empty_query(
    session: AsyncSession,
) -> None:
    assert await search_sellers(session, "", limit=10) == []
    assert await search_sellers(session, "   ", limit=10) == []


async def test_search_sellers_treats_wildcards_as_literal_text(
    session: AsyncSession,
) -> None:
    # "%" chưa thoát sẽ khớp mọi người bán; đây là chuỗi tự do người dùng gõ vào.
    assert await search_sellers(session, "%", limit=10) == []


async def test_search_sellers_counts_are_unfiltered_totals(
    session: AsyncSession,
) -> None:
    # Cùng lý do với list_customer_states: chọn một tuỳ chọn không được làm biến mất
    # hay thu nhỏ các tuỳ chọn còn lại. Số đơn trên gợi ý là tổng của cả bộ dữ liệu.
    seller_id = EDGE_CASE_FILTERS["busiest_seller"]
    expected = (
        await compute_kpis(session, DashboardFilters(seller_id=seller_id))
    ).delivered_orders

    option = (await search_sellers(session, seller_id[:8], limit=10))[0]

    assert option.delivered_orders == expected


def test_small_sample_threshold_excludes_exactly_thirty() -> None:
    assert SMALL_SAMPLE_MAX_ORDERS == 30
    assert is_small_sample(29) is True
    assert is_small_sample(30) is False
    assert is_small_sample(31) is False


async def test_a_seller_below_the_threshold_is_flagged(session: AsyncSession) -> None:
    seller_id = EDGE_CASE_FILTERS["small_sample_sellers"][0]

    kpis = await compute_kpis(session, DashboardFilters(seller_id=seller_id))

    assert 0 < kpis.delivered_orders < SMALL_SAMPLE_MAX_ORDERS
    assert is_small_sample(kpis.delivered_orders) is True


def test_previous_period_has_the_same_length_and_ends_the_day_before() -> None:
    period = ReportingPeriod(start_date=date(2018, 3, 1), end_date=date(2018, 3, 31))

    previous = resolve_comparison_period(period, "previous")

    assert previous == ReportingPeriod(
        start_date=date(2018, 1, 29), end_date=date(2018, 2, 28)
    )
    # Cùng độ dài là điều kiện để hai đường xu hướng so được với nhau.
    assert _span_days(previous) == _span_days(period)


def test_year_over_year_period_shifts_back_one_year() -> None:
    period = ReportingPeriod(start_date=date(2018, 1, 1), end_date=date(2018, 6, 30))

    assert resolve_comparison_period(period, "year_over_year") == ReportingPeriod(
        start_date=date(2017, 1, 1), end_date=date(2017, 6, 30)
    )


def test_year_over_year_clamps_the_leap_day() -> None:
    # 29/2/2016 không tồn tại ở 2015; lùi về 28/2 thay vì ném ValueError.
    period = ReportingPeriod(start_date=date(2016, 2, 29), end_date=date(2016, 2, 29))

    assert resolve_comparison_period(period, "year_over_year") == ReportingPeriod(
        start_date=date(2015, 2, 28), end_date=date(2015, 2, 28)
    )


def test_no_comparison_mode_resolves_to_nothing() -> None:
    period = ReportingPeriod(start_date=date(2018, 1, 1), end_date=date(2018, 6, 30))

    assert resolve_comparison_period(period, "none") is None
    # Chưa có đơn đã giao nào thì không có kỳ chính, nên cũng không có kỳ đối chiếu.
    assert resolve_comparison_period(None, "previous") is None


async def test_comparison_trend_uses_the_report_period_granularity(
    session: AsyncSession,
) -> None:
    """Kỳ đối chiếu không được tự chọn độ mịn của riêng nó.

    Cặp ngày này lệch nhau đúng một ngày vì 29/2/2016 nằm trong kỳ đối chiếu chứ không
    nằm trong kỳ chính, và một ngày đó đủ đẩy kỳ đối chiếu qua ngưỡng tuần/tháng.
    """
    period = ReportingPeriod(start_date=date(2016, 9, 2), end_date=date(2017, 3, 2))
    comparison = resolve_comparison_period(period, "year_over_year")

    assert comparison is not None
    # Tiền đề của chính bài test: để tự chọn thì hai kỳ ra hai độ mịn KHÁC nhau. Thiếu
    # khẳng định này, bài test vẫn xanh kể cả khi tham số granularity bị bỏ qua.
    assert _span_days(period) == 182
    assert _span_days(comparison) == 183
    assert choose_granularity(period) == "week"
    assert choose_granularity(comparison) == "month"

    granularity = choose_granularity(period)
    main = await compute_late_rate_trend(session, DashboardFilters(period=period))
    other = await compute_late_rate_trend(
        session, DashboardFilters(period=comparison), granularity=granularity
    )

    assert main.granularity == "week"
    assert other.granularity == "week"


def _span_days(period: ReportingPeriod) -> int:
    return (period.end_date - period.start_date).days + 1


def _months_spanned(period: ReportingPeriod) -> int:
    start, end = period.start_date, period.end_date
    return (end.year - start.year) * 12 + end.month - start.month + 1
