import json
from functools import partial
from pathlib import Path

import pytest

from app.risk.candidates import SklearnQuantileStage
from app.risk.training import REPORT_FILENAME, train

# Thô hơn RISK_SAMPLE_STEP=30 của fixture mặc định (conftest.py): các bài dưới đây
# chỉ cần xác nhận hành vi tham số hoá, không cần độ chính xác của một lần huấn
# luyện thật, nên chọn bước lấy mẫu thô hơn và chỉ một thuật toán nhẹ để rẻ.
EXPERIMENT_SAMPLE_STEP = 60
REDUCED_ALGORITHMS = {"sklearn_quantile": partial(SklearnQuantileStage, max_iter=5)}


def _comparable(report: dict) -> dict:
    return {k: v for k, v in report.items() if k not in ("model_version", "trained_at")}


def _train(tmp_path_factory: pytest.TempPathFactory, **kwargs) -> dict:
    directory = tmp_path_factory.mktemp("risk_experiment")
    train(model_dir=directory, sample_step=EXPERIMENT_SAMPLE_STEP, **kwargs)
    return json.loads((directory / REPORT_FILENAME).read_text("utf-8"))


@pytest.fixture(scope="module")
def reduced_algorithms_runs(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict, dict]:
    first = _train(tmp_path_factory, algorithms=REDUCED_ALGORITHMS)
    second = _train(tmp_path_factory, algorithms=REDUCED_ALGORITHMS)
    return first, second


@pytest.fixture(scope="module")
def custom_ratio_runs(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict, dict]:
    kwargs = dict(algorithms=REDUCED_ALGORITHMS, train_ratio=0.5, validation_ratio=0.25)
    first = _train(tmp_path_factory, **kwargs)
    second = _train(tmp_path_factory, **kwargs)
    return first, second


def test_custom_algorithm_set_changes_which_algorithms_run(
    reduced_algorithms_runs: tuple[dict, dict],
) -> None:
    first, _second = reduced_algorithms_runs
    assert set(first["algorithms"]) == {"sklearn_quantile"}
    assert first["selected_algorithm"] == "sklearn_quantile"


def test_custom_algorithm_set_is_reproducible_with_same_seed(
    reduced_algorithms_runs: tuple[dict, dict],
) -> None:
    first, second = reduced_algorithms_runs
    assert _comparable(first) == _comparable(second)


def test_custom_split_ratios_are_reproducible_with_same_seed(
    custom_ratio_runs: tuple[dict, dict],
) -> None:
    first, second = custom_ratio_runs
    assert _comparable(first) == _comparable(second)


def test_custom_split_ratios_change_results_vs_default_ratios(
    reduced_algorithms_runs: tuple[dict, dict],
    custom_ratio_runs: tuple[dict, dict],
) -> None:
    """Cùng tập thuật toán, chỉ khác tỷ lệ chia -> kích thước từng tập phải khác,
    nên so sánh không lệch biến bởi thuật toán hay sample_step khác nhau."""
    default_ratio_report, _ = reduced_algorithms_runs
    custom_ratio_report, _ = custom_ratio_runs

    assert (
        custom_ratio_report["splits"]["train"]["rows"]
        != default_ratio_report["splits"]["train"]["rows"]
    )
    assert _comparable(custom_ratio_report) != _comparable(default_ratio_report)
