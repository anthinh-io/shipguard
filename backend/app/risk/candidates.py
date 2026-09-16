"""Ba bộ thuật toán ứng viên, mỗi bộ dùng một thuật toán cho cả ba chặng (ADR-0008).

Cả ba phơi ra cùng một giao diện: nhận đặc trưng, trả về một lưới phân vị của thời
gian chặng. Nhờ vậy phần lấy mẫu, phần đánh giá và phần dự đoán không cần biết bên
dưới là XGBoost hay Scikit-learn.
"""

from typing import Protocol

import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.stats import norm
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import OrdinalEncoder

from app.risk.dataset import MIN_STAGE_DAYS
from app.risk.features import CATEGORICAL_FEATURES, FEATURES

# Có 0,99 chứ không dừng ở 0,90: đuôi trên là chỗ quyết định một đơn có trễ hay không,
# nên cắt lưới ở 0,90 là bỏ đúng phần cần nhất.
QUANTILES = (0.05, 0.25, 0.50, 0.75, 0.90, 0.99)

MEDIAN_INDEX = QUANTILES.index(0.50)


class FeatureEncoder:
    """Đưa cột phân loại về mã số nguyên; mọi thứ khác giữ nguyên dạng số.

    Mã số nguyên chứ không phải cột phân loại gốc của từng thư viện: ba thư viện khai
    báo cột phân loại theo ba kiểu khác nhau, và HistGradientBoosting còn chặn cứng ở
    255 mức trong khi `route` có tới hơn sáu trăm. Một đường mã hoá chung đổi lấy việc
    cây phải tách nhiều nhánh hơn cho cùng một nhóm mức — chấp nhận được, và đã có
    `distance_km` gánh phần tổng quát hoá theo tuyến.
    """

    def __init__(self) -> None:
        self._encoder = OrdinalEncoder(
            handle_unknown="use_encoded_value",
            unknown_value=-1,
            encoded_missing_value=-1,
        )

    def fit(self, frame: pd.DataFrame) -> "FeatureEncoder":
        self._encoder.fit(self._categoricals(frame))
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        encoded = frame.reindex(columns=list(FEATURES)).copy()
        encoded[list(CATEGORICAL_FEATURES)] = self._encoder.transform(
            self._categoricals(frame)
        )
        return encoded.astype(float)

    @staticmethod
    def _categoricals(frame: pd.DataFrame) -> pd.DataFrame:
        # astype(str) chứ không để nguyên: thiếu danh mục là NaN, và NaN so sánh không
        # bằng chính nó nên OrdinalEncoder coi mỗi lần gặp là một mức mới.
        return frame.reindex(columns=list(CATEGORICAL_FEATURES)).astype(str)


def _finalise(raw: np.ndarray) -> np.ndarray:
    """Ép lưới phân vị không giảm rồi kẹp sàn.

    Hồi quy phân vị không đảm bảo các phân vị khỏi cắt nhau — mỗi phân vị là một mô
    hình riêng. Để nguyên thì hàm phân phối ngược không đơn điệu và phép lấy mẫu trả
    về số vô nghĩa.
    """
    return np.clip(np.maximum.accumulate(raw, axis=1), MIN_STAGE_DAYS, None)


class StageModel(Protocol):
    def fit(self, features: pd.DataFrame, target: np.ndarray) -> None: ...

    def predict_quantiles(self, features: pd.DataFrame) -> np.ndarray:
        """(số dòng, len(QUANTILES)), không giảm theo cột, đã kẹp sàn."""

    def feature_importances(self) -> np.ndarray | None:
        """Một điểm cho mỗi cột trong FEATURES, hoặc None nếu thuật toán không cho.

        Có mặt ở đây để notebook phân tích không phải thọc vào thuộc tính riêng của
        từng thư viện — đúng lời hứa ở đầu tệp này, rằng bên gọi không cần biết bên
        dưới là XGBoost hay Scikit-learn.
        """


class XGBQuantileStage:
    """XGBoost hồi quy phân vị — một mô hình cho cả sáu phân vị."""

    def __init__(self) -> None:
        self._model = xgb.XGBRegressor(
            objective="reg:quantileerror",
            quantile_alpha=np.array(QUANTILES),
            n_estimators=300,
            learning_rate=0.1,
            max_depth=6,
            random_state=0,
        )

    def fit(self, features: pd.DataFrame, target: np.ndarray) -> None:
        self._model.fit(features, target)

    def predict_quantiles(self, features: pd.DataFrame) -> np.ndarray:
        return _finalise(np.asarray(self._model.predict(features), dtype=float))

    def feature_importances(self) -> np.ndarray | None:
        return np.asarray(self._model.feature_importances_, dtype=float)


class XGBAftStage:
    """XGBoost phân phối log-normal (AFT).

    Mô hình học vị trí của log(thời gian); độ lệch chuẩn không được học cùng, nên nó
    được ước lượng từ phần dư trên chính tập huấn luyện. Đặt đại một hằng số thì các
    phân vị rộng hay hẹp tuỳ may rủi.
    """

    def __init__(self) -> None:
        self._booster: xgb.Booster | None = None
        self._sigma = 1.0

    def fit(self, features: pd.DataFrame, target: np.ndarray) -> None:
        matrix = xgb.DMatrix(features)
        matrix.set_float_info("label_lower_bound", target)
        matrix.set_float_info("label_upper_bound", target)
        self._booster = xgb.train(
            {
                "objective": "survival:aft",
                "aft_loss_distribution": "normal",
                "aft_loss_distribution_scale": 1.0,
                "learning_rate": 0.1,
                "max_depth": 6,
                "seed": 0,
            },
            matrix,
            num_boost_round=300,
        )
        fitted = np.asarray(self._booster.predict(matrix), dtype=float)
        residual = np.log(target) - np.log(np.clip(fitted, MIN_STAGE_DAYS, None))
        self._sigma = float(np.std(residual)) or 1.0

    def predict_quantiles(self, features: pd.DataFrame) -> np.ndarray:
        assert self._booster is not None, "fit phải chạy trước predict_quantiles"
        location = np.asarray(self._booster.predict(xgb.DMatrix(features)), dtype=float)
        spread = np.exp(self._sigma * norm.ppf(np.array(QUANTILES)))
        return _finalise(location[:, None] * spread[None, :])

    def feature_importances(self) -> np.ndarray | None:
        if self._booster is None:
            return None
        # Booster đánh số cột là f0, f1, ... và bỏ hẳn cột không được cây nào dùng,
        # nên phải điền 0 vào chỗ trống để độ dài khớp danh sách đặc trưng.
        scores = self._booster.get_score(importance_type="gain")
        return np.array(
            [scores.get(f"f{index}", 0.0) for index in range(len(FEATURES))], dtype=float
        )


class SklearnQuantileStage:
    """Scikit-learn HistGradientBoosting hồi quy phân vị — một mô hình mỗi phân vị."""

    def __init__(self) -> None:
        self._models = [
            HistGradientBoostingRegressor(
                loss="quantile",
                quantile=quantile,
                max_iter=200,
                learning_rate=0.1,
                random_state=0,
            )
            for quantile in QUANTILES
        ]

    def fit(self, features: pd.DataFrame, target: np.ndarray) -> None:
        for model in self._models:
            model.fit(features, target)

    def predict_quantiles(self, features: pd.DataFrame) -> np.ndarray:
        columns = [model.predict(features) for model in self._models]
        return _finalise(np.column_stack(columns).astype(float))

    def feature_importances(self) -> np.ndarray | None:
        # HistGradientBoostingRegressor không có feature_importances_; muốn biết thì
        # phải chạy permutation importance, vốn cần dữ liệu và tốn thời gian, nên
        # không phải việc của một thuộc tính đọc ra là có.
        return None


ALGORITHMS = {
    "xgboost_quantile": XGBQuantileStage,
    "xgboost_aft": XGBAftStage,
    "sklearn_quantile": SklearnQuantileStage,
}


def sample_days(quantile_values: np.ndarray, uniforms: np.ndarray) -> np.ndarray:
    """Lấy mẫu thời gian chặng bằng nội suy ngược trên lưới phân vị.

    quantile_values: (số dòng, số phân vị). uniforms: (số dòng, số mẫu).

    Ngoài hai đầu lưới thì ngoại suy tuyến tính theo đoạn ngoài cùng chứ không kẹp:
    kẹp ở phân vị 0,99 biến mọi đuôi dài thành đúng một giá trị, mà đuôi dài lại là
    thứ sinh ra đơn trễ. Sàn dương vẫn giữ để đầu dưới không âm.
    """
    grid = np.array(QUANTILES)
    lower = np.clip(np.searchsorted(grid, uniforms, side="right") - 1, 0, len(grid) - 2)
    upper = lower + 1

    span = grid[upper] - grid[lower]
    fraction = (uniforms - grid[lower]) / span
    low_value = np.take_along_axis(quantile_values, lower, axis=1)
    high_value = np.take_along_axis(quantile_values, upper, axis=1)
    return np.clip(
        low_value + fraction * (high_value - low_value), MIN_STAGE_DAYS, None
    )
