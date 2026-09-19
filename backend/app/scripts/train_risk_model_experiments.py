"""Huấn luyện lần lượt các biến thể để so sánh chất lượng — không đụng RISK_MODEL_DIR.

Không nhận tham số dòng lệnh: danh sách biến thể khai báo ngay dưới đây, cùng khuôn với
train_risk_model.py. Mỗi biến thể gọi đúng train() ở app.risk.training (tham số hoá ở #43/#44),
ghi vào một thư mục con riêng dưới EXPERIMENTS_DIR — một vị trí tách biệt hẳn khỏi
RISK_MODEL_DIR nên không ảnh hưởng mô hình đang phục vụ backend.
"""

import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import partial

from app.core.config import settings
from app.risk.candidates import (
    ALGORITHMS,
    LightGBMQuantileStage,
    SklearnQuantileStage,
    StageModel,
    XGBAftStage,
    XGBQuantileStage,
)
from app.risk.training import REPORT_FILENAME, format_summary, train

# Sibling của RISK_MODEL_DIR (mặc định models/), không phải thư mục con của nó — đảm bảo tách biệt
# khỏi nơi backend đọc mô hình đang phục vụ dù RISK_MODEL_DIR được cấu hình trỏ đi đâu.
EXPERIMENTS_DIR = settings.RISK_MODEL_DIR.parent / "experiments"


@dataclass(frozen=True)
class Variant:
    name: str
    algorithms: Mapping[str, Callable[[], StageModel]] = field(default_factory=lambda: ALGORITHMS)
    train_ratio: float = 0.70
    validation_ratio: float = 0.15


VARIANTS = [
    Variant(name="baseline"),
    # Siêu tham số của ba thuật toán hiện có — mỗi biến thể áp cho cả ba cùng lúc.
    Variant(
        name="hyperparam_deeper_trees",
        algorithms={
            "xgboost_quantile": partial(XGBQuantileStage, max_depth=8, n_estimators=400),
            "xgboost_aft": partial(XGBAftStage, max_depth=8, num_boost_round=400),
            "sklearn_quantile": partial(SklearnQuantileStage, max_iter=300),
        },
    ),
    Variant(
        name="hyperparam_shallower_trees",
        algorithms={
            "xgboost_quantile": partial(XGBQuantileStage, max_depth=4, n_estimators=200),
            "xgboost_aft": partial(XGBAftStage, max_depth=4, num_boost_round=200),
            "sklearn_quantile": partial(SklearnQuantileStage, max_iter=150),
        },
    ),
    Variant(
        name="hyperparam_slow_learning_rate",
        algorithms={
            "xgboost_quantile": partial(XGBQuantileStage, learning_rate=0.05, n_estimators=600),
            "xgboost_aft": partial(XGBAftStage, learning_rate=0.05, num_boost_round=600),
            "sklearn_quantile": partial(SklearnQuantileStage, learning_rate=0.05, max_iter=400),
        },
    ),
    Variant(
        name="hyperparam_fast_learning_rate",
        algorithms={
            "xgboost_quantile": partial(XGBQuantileStage, learning_rate=0.2, n_estimators=150),
            "xgboost_aft": partial(XGBAftStage, learning_rate=0.2, num_boost_round=150),
            "sklearn_quantile": partial(SklearnQuantileStage, learning_rate=0.2, max_iter=100),
        },
    ),
    # LightGBM — không nằm trong ALGORITHMS mặc định, chỉ thử qua đây (candidates.py:254-260).
    Variant(
        name="lightgbm_default",
        algorithms={"lightgbm_quantile": partial(LightGBMQuantileStage)},
    ),
    Variant(
        name="lightgbm_deeper",
        algorithms={
            "lightgbm_quantile": partial(LightGBMQuantileStage, max_depth=10, n_estimators=500),
        },
    ),
    # Tỷ lệ chia tập khác 70/15/15 mặc định.
    Variant(name="split_60_20_20", train_ratio=0.60, validation_ratio=0.20),
    Variant(name="split_80_10_10", train_ratio=0.80, validation_ratio=0.10),
    Variant(name="split_75_10_15", train_ratio=0.75, validation_ratio=0.10),
]


def main() -> None:
    # Cùng lý do với train_risk_model.py: console Windows mặc định cp1252, dừng hẳn với
    # UnicodeEncodeError ở chữ có dấu đầu tiên.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print(f"Chạy {len(VARIANTS)} biến thể, ghi vào {EXPERIMENTS_DIR}\n")

    for variant in VARIANTS:
        model_dir = EXPERIMENTS_DIR / variant.name
        report = train(
            model_dir=model_dir,
            algorithms=variant.algorithms,
            train_ratio=variant.train_ratio,
            validation_ratio=variant.validation_ratio,
        )
        print(f"=== {variant.name} ===")
        print(format_summary(report))
        print(f"Đã ghi vào {model_dir}; báo cáo đầy đủ ở {REPORT_FILENAME}.")
        print()


if __name__ == "__main__":
    main()
