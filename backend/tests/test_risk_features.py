import math

import numpy as np
import pandas as pd
import pytest

from app.risk.dataset import TrainingData, load_training_data
from app.risk.features import FEATURES, HISTORY_COLUMNS, build_features, haversine_km


@pytest.fixture(scope="module")
def data() -> TrainingData:
    return load_training_data(sample_step=20)


def _trim(data: TrainingData, order_count: int) -> TrainingData:
    orders = data.orders.iloc[:order_count]
    keep = set(orders["order_id"])
    return TrainingData(
        orders=orders,
        lines=data.lines[data.lines["order_id"].isin(keep)],
        payments=data.payments[data.payments["order_id"].isin(keep)],
        zip_coords=data.zip_coords,
        excluded=data.excluded,
    )


def _build(data: TrainingData):
    return build_features(data.orders, data.lines, data.payments, data.zip_coords)


def test_every_declared_feature_is_present_in_both_grains(data: TrainingData) -> None:
    features = _build(data)

    for frame in (features.order_level, features.seller_level):
        assert set(FEATURES) <= set(frame.columns)
    assert len(features.order_level) == len(data.orders)
    assert len(features.seller_level) >= len(features.order_level)


def test_features_do_not_change_when_later_orders_are_appended(data: TrainingData) -> None:
    """Bài canh rò rỉ thời gian.

    "Đơn đầu tiên của một người bán có 0 đơn trước" là cần nhưng chưa đủ: một phép
    trung bình trên toàn nhóm cũng thoả điều kiện đó ở dòng đầu tiên. Thứ duy nhất
    phân biệt được là bất biến với tương lai — thêm đơn đặt muộn hơn vào dữ liệu thì
    đặc trưng của các đơn cũ không được nhúc nhích.
    """
    earlier = _build(_trim(data, 400)).order_level.set_index("order_id")
    with_future = (
        _build(_trim(data, 800)).order_level.set_index("order_id").loc[earlier.index]
    )

    pd.testing.assert_frame_equal(earlier[list(FEATURES)], with_future[list(FEATURES)])


def test_features_do_not_depend_on_input_row_order(data: TrainingData) -> None:
    trimmed = _trim(data, 400)
    shuffled = TrainingData(
        orders=trimmed.orders.sample(frac=1, random_state=7),
        lines=trimmed.lines.sample(frac=1, random_state=7),
        payments=trimmed.payments.sample(frac=1, random_state=7),
        zip_coords=trimmed.zip_coords,
        excluded=trimmed.excluded,
    )

    pd.testing.assert_frame_equal(
        _build(trimmed).order_level[list(FEATURES)],
        _build(shuffled).order_level[list(FEATURES)],
    )


def test_a_sellers_first_order_has_no_history(data: TrainingData) -> None:
    seller_level = _build(data).seller_level
    first_orders = seller_level[seller_level["seller_prior_orders"] == 0]

    assert len(first_orders) > 0
    # NaN chứ không phải 0: người bán chưa có đơn nào trước đó thì tỷ lệ trễ trong quá
    # khứ không tồn tại. Điền 0 là nói rằng họ chưa bao giờ giao trễ.
    for column in HISTORY_COLUMNS[1:]:
        assert first_orders[column].isna().all()
    # Và người bán có đơn trước thì phải có số, nếu không phép tính hỏng ở chỗ khác.
    repeat = seller_level[seller_level["seller_prior_orders"] > 0]
    assert repeat["seller_prior_late_rate"].notna().all()


def test_distance_matches_an_independent_haversine(data: TrainingData) -> None:
    seller_level = _build(data).seller_level
    row = seller_level[seller_level["distance_km"].notna()].iloc[0]
    coords = data.zip_coords

    seller = coords.loc[row["seller_zip"]]
    customer = coords.loc[row["customer_zip"]]
    # Công thức viết tay bằng math, không gọi lại hàm đang kiểm.
    lat1, lng1, lat2, lng2 = map(
        math.radians, [seller["lat"], seller["lng"], customer["lat"], customer["lng"]]
    )
    inner = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    )
    expected = 2 * 6371.0088 * math.asin(math.sqrt(inner))

    assert row["distance_km"] == pytest.approx(expected, abs=1.0)


def test_missing_coordinates_give_nan_distance_not_zero(data: TrainingData) -> None:
    seller_level = _build(data).seller_level

    missing = seller_level["distance_km"].isna()
    # Vài mã bưu chính không có trong bảng toạ độ. Chúng phải ra NaN — điền 0 là nói
    # rằng người bán ở ngay cạnh khách, tức tín hiệu ngược hẳn sự thật.
    assert missing.mean() < 0.01
    assert haversine_km(
        pd.Series([np.nan]), pd.Series([0.0]), pd.Series([0.0]), pd.Series([0.0])
    )[0] != 0.0


def test_zip_codes_keep_their_leading_zero(data: TrainingData) -> None:
    # Cột mã bưu chính trong bảng tạm của bước dựng là INTEGER nên 01310 đã thành 1310;
    # đọc thẳng CSV thì không. Nếu ai đó bỏ dtype=str, phép nối bảng toạ độ lệch câm.
    assert data.orders["customer_zip"].str.startswith("0").any()
    assert data.zip_coords.index.str.startswith("0").any()
    assert data.orders["customer_zip"].str.len().eq(5).all()
