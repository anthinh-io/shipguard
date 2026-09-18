import csv
import json
from pathlib import Path

import pytest

from app.risk.candidates import ALGORITHMS
from app.risk.dataset import STAGES
from app.risk.predictor import CHECKPOINTS, MODEL_FILENAME
from app.risk.training import (
    METRICS_FILENAME,
    PREDICTIONS_FILENAME,
    REPORT_FILENAME,
    format_summary,
)
from conftest import comparable_report

# Bộ test huấn luyện trên một phần dữ liệu, nên F1 ở đây vô nghĩa và KHÔNG bài nào
# khẳng định F1 >= 0,30. Tiêu chí chấp nhận cũng cho phép dưới mục tiêu, miễn báo cáo
# ghi rõ. Mục tiêu được kiểm bằng một lần chạy đầy đủ, ghi lại trong backend/README.md.


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def report(risk_model_dir: Path) -> dict:
    return json.loads((risk_model_dir / REPORT_FILENAME).read_text("utf-8"))


def test_default_call_matches_pre_parameterization_baseline(report: dict) -> None:
    """An toàn ngược: gọi train() không truyền algorithms/train_ratio/validation_ratio
    phải cho kết quả giống hệt bản chụp trước khi tham số hoá (Issue #43)."""
    baseline = json.loads((FIXTURES / "risk_report_baseline.json").read_text("utf-8"))
    assert comparable_report(report) == baseline


def test_training_writes_model_and_report_files(risk_model_dir: Path) -> None:
    assert sorted(path.name for path in risk_model_dir.iterdir()) == sorted(
        [MODEL_FILENAME, REPORT_FILENAME, METRICS_FILENAME, PREDICTIONS_FILENAME]
    )


def test_report_scores_every_algorithm_at_every_checkpoint(report: dict) -> None:
    assert set(report["algorithms"]) == set(ALGORITHMS)

    for evaluation in report["algorithms"].values():
        for checkpoint in CHECKPOINTS:
            scored = evaluation["test"][checkpoint]["at_selected_threshold"]
            assert set(scored) >= {"precision", "recall", "f1", "accuracy"}
            assert all(
                0.0 <= scored[name] <= 1.0
                for name in ("precision", "recall", "f1", "accuracy")
            )
            assert 0.0 <= evaluation["validation"][checkpoint]["f1"] <= 1.0
            roc = evaluation["test"][checkpoint]["roc_auc"]
            assert roc is None or 0.0 <= roc <= 1.0


def test_suggested_threshold_is_a_usable_probability(report: dict) -> None:
    threshold = report["suggested_risk_threshold"]

    assert 0.0 < threshold < 1.0
    # Ngưỡng xấp xỉ 0,5 là dấu hiệu đang dò trên sai tập: tỷ lệ trễ nền chỉ khoảng
    # 6,8%, nên gần như không đơn nào vượt 0,5 ở mốc đặt hàng.
    assert threshold < 0.45


def test_model_is_written_even_when_the_f1_target_is_missed(
    report: dict, risk_model_dir: Path
) -> None:
    assert isinstance(report["meets_f1_target"], bool)
    assert report["meets_f1_target"] == (report["f1_at_order_placed"] >= report["f1_target"])
    assert (risk_model_dir / MODEL_FILENAME).exists()


def test_report_carries_the_context_needed_to_read_the_scores(report: dict) -> None:
    assert report["model_version"]
    assert set(report["historical_median_days"]) == set(STAGES)
    assert report["selected_algorithm"] in ALGORITHMS

    # Tỷ lệ trễ từng tập phải có mặt: nó tụt từ ~7,8% xuống ~4,3% theo thời gian, nên
    # thiếu con số này thì F1 trong báo cáo không đọc được đúng nghĩa.
    for name in ("train", "validation", "test"):
        split = report["splits"][name]
        assert split["rows"] > 0
        assert 0.0 < split["late_rate"] < 1.0
    assert report["splits"]["train"]["to"] <= report["splits"]["test"]["from"]

    assert report["excluded_orders"]["handed_before_purchase"] == 165
    assert report["excluded_orders"]["handed_after_delivery"] == 23


def test_metrics_csv_has_one_row_per_algorithm_and_checkpoint(
    risk_model_dir: Path,
) -> None:
    with open(risk_model_dir / METRICS_FILENAME, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == len(ALGORITHMS) * len(CHECKPOINTS)
    assert {row["algorithm"] for row in rows} == set(ALGORITHMS)
    assert {row["checkpoint"] for row in rows} == set(CHECKPOINTS)
    assert set(rows[0]) == {
        "algorithm", "checkpoint", "precision", "recall", "f1", "accuracy", "roc_auc",
    }


def test_summary_names_the_threshold_to_configure(report: dict) -> None:
    summary = format_summary(report)

    assert f"RISK_THRESHOLD={report['suggested_risk_threshold']}" in summary
    assert ("ĐẠT" in summary) or ("CHƯA ĐẠT" in summary)
    assert "Accuracy" in summary
    assert "ROC-AUC" in summary
    for algorithm in ALGORITHMS:
        assert algorithm in summary
