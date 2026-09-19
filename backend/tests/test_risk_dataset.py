import pandas as pd
import pytest

from app.risk.dataset import MIN_STAGE_DAYS, STAGES, load_training_data, split_by_purchase_time

# Bộ số vàng của dữ liệu huấn luyện. Đo thẳng trên cơ sở dữ liệu đã dựng, còn các bài
# dưới đây tính lại từ tệp CSV — hai đường độc lập, nên một lỗi ở đường này không tự
# bào chữa bằng đường kia. Cùng lý do với tests/test_order_value_golden.py.
DELIVERED = 96_470
KEPT = 96_267
HANDED_BEFORE_PURCHASE = 165
HANDED_AFTER_DELIVERY = 23
MISSING_MILESTONE = 15

LATE = 6_531
# Con số nhận được khi so nguyên dấu thời gian thay vì ngày lịch. Không phải một hằng
# số vu vơ: đây là giá trị mà một lần sửa "cho gọn" sẽ vô tình tạo ra, và chênh 20%.
LATE_BY_TIMESTAMP = 7_822

# Số dòng bị sàn nâng, đo bằng SQL với cùng vị từ "nhỏ hơn hoặc bằng một phút". Tách
# ra hai phần vì chúng nói hai chuyện khác nhau: phần âm-hoặc-0 là đặc thù ghi nhận
# của Olist, phần còn lại chỉ là chặng nhanh hơn một phút.
FLOORED = {
    "payment_approval": 1_243,  # 1.243 đúng bằng 0, không đơn nào âm
    "seller_handling": 1_188,  # 1.185 âm (bàn giao trước khi duyệt) + 3 dưới một phút
    "carrier_transit": 15,  # 9 đúng bằng 0 + 6 dưới một phút
}


@pytest.fixture(scope="module")
def data():
    return load_training_data()


def test_only_impossible_timelines_are_excluded(data) -> None:
    assert data.excluded == {
        "delivered": DELIVERED,
        "handed_before_purchase": HANDED_BEFORE_PURCHASE,
        "handed_after_delivery": HANDED_AFTER_DELIVERY,
        "missing_milestone": MISSING_MILESTONE,
        "kept": KEPT,
    }
    assert len(data.orders) == KEPT
    assert (
        DELIVERED - HANDED_BEFORE_PURCHASE - HANDED_AFTER_DELIVERY - MISSING_MILESTONE
        == KEPT
    )


def test_late_labels_compare_calendar_dates_not_timestamps(data) -> None:
    orders = data.orders

    assert orders["is_late"].sum() == LATE

    # Ngày cam kết trong dữ liệu Olist luôn ở lúc nửa đêm, nên so nguyên dấu thời gian
    # biến "giao đúng ngày cam kết lúc 9 giờ sáng" thành trễ.
    by_timestamp = orders["delivered_to_customer_at"] > orders["estimated_delivery_date"]
    assert by_timestamp.sum() == LATE_BY_TIMESTAMP
    assert orders["is_late"].sum() != LATE_BY_TIMESTAMP


@pytest.mark.parametrize("stage", STAGES)
def test_stage_labels_are_strictly_positive_after_flooring(data, stage: str) -> None:
    labels = data.orders[stage]

    assert labels.notna().all()
    assert (labels >= MIN_STAGE_DAYS).all()
    # Số dòng đúng bằng sàn: chặng âm hoặc bằng 0 trước khi kẹp. Giữ chúng lại thay vì
    # loại là quyết định có chủ đích — xem chú thích trong dataset.py.
    assert (labels == MIN_STAGE_DAYS).sum() == FLOORED[stage]


def test_splits_follow_purchase_time_without_overlapping(data) -> None:
    splits = split_by_purchase_time(data.orders)

    assert list(splits) == ["train", "validation", "test"]
    assert sum(len(part) for part in splits.values()) == KEPT
    assert len(splits["train"]) == int(KEPT * 0.70)
    assert len(splits["validation"]) == int(KEPT * 0.15)

    bounds = [
        (part["purchased_at"].min(), part["purchased_at"].max())
        for part in splits.values()
    ]
    for (_, earlier_end), (later_start, _) in zip(bounds, bounds[1:]):
        assert earlier_end <= later_start

    # Tỷ lệ trễ tụt mạnh theo thời gian, nên F1 trên tập kiểm tra không so được với F1
    # trên dữ liệu trộn ngẫu nhiên. Bài này giữ cho sự thật đó không bị quên.
    rates = [part["is_late"].mean() for part in splits.values()]
    assert rates[0] > rates[2]
    assert rates[2] < 0.05


def test_splits_respect_custom_ratios(data) -> None:
    splits = split_by_purchase_time(data.orders, train_ratio=0.5, validation_ratio=0.25)

    assert list(splits) == ["train", "validation", "test"]
    assert sum(len(part) for part in splits.values()) == KEPT
    assert len(splits["train"]) == int(KEPT * 0.5)
    assert len(splits["validation"]) == int(KEPT * 0.25)
    assert len(splits["train"]) != int(KEPT * 0.70)


def test_sample_step_thins_the_rows_but_keeps_the_time_span() -> None:
    thinned = load_training_data(sample_step=40)

    assert len(thinned.orders) == pytest.approx(KEPT / 40, rel=0.01)
    assert thinned.orders["purchased_at"].max() > pd.Timestamp("2018-08-01")
    assert thinned.orders["purchased_at"].min() < pd.Timestamp("2017-01-01")
