from datetime import date, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from app.risk.candidates import MEDIAN_INDEX
from app.risk.dataset import STAGES
from app.risk.features import build_features
from app.risk.predictor import (
    MODEL_FILENAME,
    OrderInput,
    OrderLine,
    RiskPredictor,
    _frames_for,
    _max_within_order,
    deadline_days,
    rng_for,
    simulate,
)

PURCHASED_AT = datetime(2018, 5, 2, 10, 0)
ESTIMATED = date(2018, 5, 20)


@pytest.fixture(scope="module")
def predictor(risk_model_dir: Path) -> RiskPredictor:
    return RiskPredictor.load(risk_model_dir)


@pytest.fixture(scope="module")
def bundle(risk_model_dir: Path):
    return joblib.load(risk_model_dir / MODEL_FILENAME)


@pytest.fixture(scope="module")
def known_sellers(bundle) -> list[str]:
    return list(bundle.seller_history.index[:2])


def _line(seller_id: str, price: float = 100.0, weight: float = 900.0) -> OrderLine:
    return OrderLine(
        seller_id=seller_id,
        seller_state="SP",
        seller_zip="01310",
        product_category_name="cama_mesa_banho",
        product_weight_g=weight,
        price=price,
        freight_value=15.0,
    )


def _order(sellers: list[str], **overrides) -> OrderInput:
    return OrderInput(
        order_id=overrides.pop("order_id", "test-order-0001"),
        purchased_at=PURCHASED_AT,
        estimated_delivery_date=ESTIMATED,
        customer_state="BA",
        customer_zip="40010",
        lines=tuple(_line(seller) for seller in sellers),
        payment_types=("credit_card",),
        payment_installments=3,
        **overrides,
    )


# --- Các phép tính lõi, kiểm bằng số dựng sẵn thay vì qua mô hình -------------------


def test_deadline_runs_to_the_end_of_the_promised_day() -> None:
    days = deadline_days(
        pd.Series([pd.Timestamp("2018-01-01 10:00")]),
        pd.Series([pd.Timestamp("2018-01-05")]),
    )

    # Giao đúng ngày cam kết là đúng hạn bất kể mấy giờ, nên hạn chót là nửa đêm sang
    # ngày 6, tức 4 ngày 14 giờ sau lúc đặt. Lấy nhầm nửa đêm ngày 5 thì mọi xác suất
    # trễ cao lên một cách có hệ thống.
    assert days[0] == pytest.approx(4 + 14 / 24)


def test_order_waits_for_its_slowest_seller() -> None:
    fast = np.full((1, 4), 1.0)
    slow = np.full((1, 4), 9.0)

    combined = _max_within_order(np.vstack([fast, slow]), np.array([0, 0]))

    assert combined.shape == (1, 4)
    assert combined.tolist() == [[9.0, 9.0, 9.0, 9.0]]


def test_settled_stages_use_real_time_instead_of_being_sampled() -> None:
    # Chặng chưa xong lấy mẫu quanh 10 ngày; chặng đã xong đóng cứng ở 30 ngày. Nếu
    # thời gian thật bị bỏ qua thì tổng không bao giờ vượt hạn 25 ngày.
    grid = np.full((1, 6), 10.0)
    probability, _ = simulate(
        quantiles={"seller_handling": grid, "carrier_transit": grid},
        settled={"payment_approval": np.array([30.0])},
        order_codes=np.array([0]),
        order_count=1,
        deadline=np.array([25.0]),
        generator=rng_for("x"),
        samples=50,
    )

    assert probability[0] == 1.0


# --- Qua bộ mô hình đã huấn luyện ---------------------------------------------------


def test_same_order_gives_the_same_probability_twice(
    predictor: RiskPredictor, known_sellers: list[str]
) -> None:
    order = _order(known_sellers[:1])

    assert predictor.predict(order).late_probability == predictor.predict(
        order
    ).late_probability


def test_probability_survives_reloading_the_model(
    risk_model_dir: Path, known_sellers: list[str]
) -> None:
    """Hạt giống phải nằm trong lời gọi, không phải trong trạng thái của tiến trình.

    Một Generator dùng chung cho cả tiến trình vẫn qua được bài ở trên nếu hai lần gọi
    tình cờ cùng trạng thái, nhưng hỏng ngay khi máy chủ khởi động lại. Bài này nạp
    lại mô hình từ đĩa thành hai đối tượng độc lập.
    """
    order = _order(known_sellers[:1])

    first = RiskPredictor.load(risk_model_dir).predict(order)
    second = RiskPredictor.load(risk_model_dir).predict(order)

    assert first.late_probability == second.late_probability
    assert first.risk_cause.stage == second.risk_cause.stage


def test_a_fresh_order_has_nothing_settled_and_still_names_a_cause(
    predictor: RiskPredictor, known_sellers: list[str]
) -> None:
    result = predictor.predict(_order(known_sellers[:1]))

    assert result.checkpoint == "order_placed"
    assert all(stage.actual_days is None for stage in result.stages)
    assert {stage.stage for stage in result.stages} == set(STAGES)
    assert 0.0 <= result.late_probability <= 1.0

    cause = result.risk_cause
    assert cause.stage in STAGES
    # Nguyên nhân phải nói được bằng số ngày so với mức thường, nếu không nhân viên
    # không có cơ sở nào để chọn biện pháp.
    forecast = next(stage for stage in result.stages if stage.stage == cause.stage)
    assert cause.excess_days == pytest.approx(
        forecast.median_days - forecast.historical_median_days
    )


def test_handed_over_order_keeps_real_times_and_can_only_blame_the_carrier(
    predictor: RiskPredictor, known_sellers: list[str]
) -> None:
    order = _order(
        known_sellers[:1],
        payment_approved_at=datetime(2018, 5, 2, 11, 0),
        handed_to_carrier_at=datetime(2018, 5, 4, 9, 0),
    )

    result = predictor.predict(order)

    assert result.checkpoint == "handed_to_carrier"
    settled = {stage.stage: stage.actual_days for stage in result.stages}
    assert settled["payment_approval"] == pytest.approx(1 / 24)
    assert settled["seller_handling"] == pytest.approx(1 + 22 / 24)
    assert settled["carrier_transit"] is None
    # Hai chặng đầu đã xảy ra rồi thì có chậm cũng không can thiệp được nữa.
    assert result.risk_cause.stage == "carrier_transit"
    assert result.risk_cause.seller_id is None


def test_approved_order_settles_only_the_payment_stage(
    predictor: RiskPredictor, known_sellers: list[str]
) -> None:
    order = _order(
        known_sellers[:1], payment_approved_at=datetime(2018, 5, 3, 10, 0)
    )

    result = predictor.predict(order)

    assert result.checkpoint == "payment_approved"
    settled = {stage.stage: stage.actual_days for stage in result.stages}
    assert settled["payment_approval"] == pytest.approx(1.0)
    assert settled["seller_handling"] is None
    assert result.risk_cause.stage in ("seller_handling", "carrier_transit")


def test_multi_seller_cause_names_the_slowest_seller(
    predictor: RiskPredictor, bundle, known_sellers: list[str]
) -> None:
    """Không đặt điều kiện quanh phần khẳng định.

    Một bài chỉ kiểm "khi nguyên nhân tình cờ rơi vào chặng người bán" thì xanh cả khi
    nêu nhầm tên, và xanh cả khi nguyên nhân không bao giờ rơi vào chặng đó. Ở đây tên
    kỳ vọng được tính lại bằng đường riêng, rồi chặng người bán bị ép thành nguyên
    nhân bằng cách chỉ để lại nó trong danh sách chặng chưa xong.
    """
    order = _order(known_sellers, order_id="multi-seller-0001")
    features = build_features(
        *_frames_for(order), bundle.zip_coords, history=bundle.seller_history
    )
    grid = bundle.stage_models["seller_handling"].predict_quantiles(
        bundle.encoder.transform(features.seller_level)
    )
    slowest = str(
        features.seller_level["seller_id"].iloc[int(grid[:, MEDIAN_INDEX].argmax())]
    )

    assert len(features.seller_level) == 2
    assert slowest in set(known_sellers)

    named = RiskPredictor._cause(
        tuple(
            stage
            for stage in predictor.predict(order).stages
            if stage.stage == "seller_handling"
        ),
        {"seller_handling": grid},
        features,
    )

    assert named.stage == "seller_handling"
    assert named.seller_id == slowest


def test_seller_is_not_named_when_another_stage_is_to_blame(
    predictor: RiskPredictor, known_sellers: list[str]
) -> None:
    result = predictor.predict(
        _order(
            known_sellers,
            order_id="multi-seller-0002",
            payment_approved_at=datetime(2018, 5, 2, 11, 0),
            handed_to_carrier_at=datetime(2018, 5, 4, 9, 0),
        )
    )

    assert result.risk_cause.stage == "carrier_transit"
    assert result.risk_cause.seller_id is None


def test_predictor_reports_the_model_version_it_was_trained_as(
    predictor: RiskPredictor, known_sellers: list[str]
) -> None:
    result = predictor.predict(_order(known_sellers[:1]))

    assert result.model_version == predictor.model_version
    assert len(predictor.model_version) == len("20260916T101500Z")


def test_missing_model_file_is_reported_as_such(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        RiskPredictor.load(tmp_path)
