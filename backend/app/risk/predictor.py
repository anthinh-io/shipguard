"""Dự đoán rủi ro giao trễ cho một đơn tại `Prediction Checkpoint` hiện tại của nó.

Mô-đun này KHÔNG đọc `RISK_THRESHOLD` và không tự phân loại `High Risk`. Mức rủi ro
được chốt lúc tạo `Risk Assessment` rồi lưu lại, nên nó thuộc về lớp gọi — xem
CONTEXT.md, mục High Risk.
"""

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.risk.candidates import MEDIAN_INDEX, FeatureEncoder, StageModel, sample_days
from app.risk.dataset import MIN_STAGE_DAYS, SECONDS_PER_DAY, STAGES
from app.risk.features import STAGE_GRAIN, build_features

MODEL_FILENAME = "risk_model.joblib"

MONTE_CARLO_SAMPLES = 2_000
RANDOM_SEED = 20260916

CHECKPOINTS = ("order_placed", "payment_approved", "handed_to_carrier")

# Chặng đã có thời gian thật tại mỗi mốc. Mốc càng muộn, càng ít thứ phải đoán.
SETTLED_AT_CHECKPOINT: dict[str, tuple[str, ...]] = {
    "order_placed": (),
    "payment_approved": ("payment_approval",),
    "handed_to_carrier": ("payment_approval", "seller_handling"),
}


@dataclass(frozen=True)
class OrderLine:
    seller_id: str
    seller_state: str
    seller_zip: str
    product_category_name: str | None
    product_weight_g: float | None
    price: float
    freight_value: float


@dataclass(frozen=True)
class OrderInput:
    order_id: str
    purchased_at: datetime
    estimated_delivery_date: date
    customer_state: str
    customer_zip: str
    lines: tuple[OrderLine, ...]
    payment_types: tuple[str, ...]
    payment_installments: int
    payment_approved_at: datetime | None = None
    handed_to_carrier_at: datetime | None = None


@dataclass(frozen=True)
class StageForecast:
    stage: str
    actual_days: float | None
    median_days: float
    historical_median_days: float
    excess_days: float


@dataclass(frozen=True)
class RiskCause:
    stage: str
    excess_days: float
    seller_id: str | None


@dataclass(frozen=True)
class RiskPrediction:
    checkpoint: str
    late_probability: float
    # Không phải kiểu tuỳ chọn: `Carrier Transit` chưa xong ở cả ba mốc dự đoán, nên
    # luôn còn ít nhất một chặng để quy nguyên nhân. Đơn đã giao thì không sinh
    # `Risk Assessment` nữa mà chuyển sang `Reconciliation`.
    risk_cause: RiskCause
    stages: tuple[StageForecast, ...]
    model_version: str


@dataclass
class ModelBundle:
    model_version: str
    algorithm: str
    encoder: FeatureEncoder
    stage_models: dict[str, StageModel]
    historical_median_days: dict[str, float]
    seller_history: pd.DataFrame
    zip_coords: pd.DataFrame


def rng_for(order_id: str) -> np.random.Generator:
    """Bộ sinh số ngẫu nhiên dựng MỚI cho mỗi lần dự đoán.

    Dùng chung một Generator giữa các lần gọi thì lần hỏi thứ hai về cùng một đơn ra
    con số khác, vì trạng thái đã tiến lên — đúng thứ tiêu chí chấp nhận canh.

    Trộn mã đơn bằng blake2b chứ không phải hash(): hash() của chuỗi trong Python đổi
    theo từng tiến trình, nên kết quả sẽ lặp lại trong một lần chạy mà khác đi ở lần
    chạy sau.
    """
    digest = hashlib.blake2b(order_id.encode(), digest_size=8).digest()
    return np.random.default_rng([RANDOM_SEED, int.from_bytes(digest, "big")])


def deadline_days(
    purchased_at: pd.Series, estimated_delivery_date: pd.Series
) -> np.ndarray:
    """Số ngày từ lúc đặt tới hết ngày cam kết.

    Trễ so theo NGÀY LỊCH: giao đúng ngày cam kết là đúng hạn bất kể mấy giờ, nên hạn
    chót là nửa đêm SANG ngày hôm sau. Bỏ quên một ngày ở đây làm mọi xác suất trễ cao
    lên một cách có hệ thống mà không có gì báo.
    """
    end_of_day = estimated_delivery_date.dt.normalize() + pd.Timedelta(days=1)
    return (end_of_day - purchased_at).dt.total_seconds().to_numpy() / SECONDS_PER_DAY


def _max_within_order(samples: np.ndarray, order_codes: np.ndarray) -> np.ndarray:
    """Gộp mẫu của nhiều người bán trong một đơn bằng phép lấy max từng lượt.

    Đơn chờ người bán chậm nhất, nên phải lấy max TRONG TỪNG lượt mô phỏng chứ không
    phải max của các trung vị: hai người bán cùng thất thường thì rủi ro cộng hưởng,
    và cách gộp sau làm mất phần cộng hưởng đó.
    """
    starts = np.flatnonzero(np.r_[True, order_codes[1:] != order_codes[:-1]])
    return np.maximum.reduceat(samples, starts, axis=0)


def simulate(
    *,
    quantiles: dict[str, np.ndarray],
    settled: dict[str, np.ndarray],
    order_codes: np.ndarray,
    order_count: int,
    deadline: np.ndarray,
    generator: np.random.Generator,
    samples: int = MONTE_CARLO_SAMPLES,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Trả về xác suất trễ mỗi đơn, và trung vị mô phỏng của từng chặng chưa xong.

    `quantiles` chứa lưới phân vị của các chặng CHƯA xong; `settled` chứa số ngày thật
    của các chặng ĐÃ xong. `seller_handling` đi ở mức (đơn, người bán) nên được gộp về
    mức đơn bằng _max_within_order.
    """
    total = np.zeros((order_count, samples))
    medians: dict[str, np.ndarray] = {}

    for stage in STAGES:
        if stage in settled:
            total += settled[stage][:, None]
            continue

        grid = quantiles[stage]
        uniforms = generator.random((grid.shape[0], samples))
        drawn = sample_days(grid, uniforms)
        if STAGE_GRAIN[stage] == "seller":
            drawn = _max_within_order(drawn, order_codes)
        total += drawn
        medians[stage] = np.median(drawn, axis=1)

    # >= chứ không phải >: đến đúng nửa đêm là đã sang ngày hôm sau, tức đã trễ.
    late = total >= deadline[:, None]
    return late.mean(axis=1), medians


class RiskPredictor:
    def __init__(self, bundle: ModelBundle) -> None:
        self._bundle = bundle

    @classmethod
    def load(cls, model_dir: Path) -> "RiskPredictor":
        path = Path(model_dir) / MODEL_FILENAME
        if not path.exists():
            raise FileNotFoundError(
                f"Chưa có tệp mô hình rủi ro ở {path}. "
                "Chạy: uv run python -m app.scripts.train_risk_model"
            )
        return cls(joblib.load(path))

    @property
    def model_version(self) -> str:
        return self._bundle.model_version

    def predict(self, order: OrderInput) -> RiskPrediction:
        checkpoint = self._checkpoint(order)
        frames = _frames_for(order)
        features = build_features(
            *frames, self._bundle.zip_coords, history=self._bundle.seller_history
        )
        encoded = {
            "order": self._bundle.encoder.transform(features.order_level),
            "seller": self._bundle.encoder.transform(features.seller_level),
        }

        settled = self._settled_days(order, checkpoint)
        quantiles = {
            stage: self._bundle.stage_models[stage].predict_quantiles(
                encoded[STAGE_GRAIN[stage]]
            )
            for stage in STAGES
            if stage not in settled
        }

        deadline = deadline_days(
            features.order_level["purchased_at"],
            features.order_level["estimated_delivery_date"],
        )
        probability, medians = simulate(
            quantiles=quantiles,
            settled={stage: np.array([value]) for stage, value in settled.items()},
            order_codes=np.zeros(len(features.seller_level), dtype=int),
            order_count=1,
            deadline=deadline,
            generator=rng_for(order.order_id),
        )

        stages = self._forecasts(settled, medians)
        return RiskPrediction(
            checkpoint=checkpoint,
            late_probability=float(probability[0]),
            risk_cause=self._cause(stages, quantiles, features),
            stages=stages,
            model_version=self._bundle.model_version,
        )

    @staticmethod
    def _checkpoint(order: OrderInput) -> str:
        """Mốc suy ra từ các mốc đã ghi nhận, không nhận từ bên ngoài.

        Hỏi một đơn đã bàn giao ở mốc đặt hàng là câu hỏi mâu thuẫn; để bên gọi tự
        khai mốc là mở đường cho nó.
        """
        if order.handed_to_carrier_at is not None:
            return "handed_to_carrier"
        if order.payment_approved_at is not None:
            return "payment_approved"
        return "order_placed"

    @staticmethod
    def _settled_days(order: OrderInput, checkpoint: str) -> dict[str, float]:
        marks = {
            "payment_approval": (order.purchased_at, order.payment_approved_at),
            "seller_handling": (order.payment_approved_at, order.handed_to_carrier_at),
        }
        settled = {}
        for stage in SETTLED_AT_CHECKPOINT[checkpoint]:
            start, end = marks[stage]
            elapsed = (end - start).total_seconds() / SECONDS_PER_DAY
            settled[stage] = max(elapsed, MIN_STAGE_DAYS)
        return settled

    def _forecasts(
        self, settled: dict[str, float], medians: dict[str, np.ndarray]
    ) -> tuple[StageForecast, ...]:
        forecasts = []
        for stage in STAGES:
            historical = self._bundle.historical_median_days[stage]
            if stage in settled:
                actual = settled[stage]
                forecasts.append(
                    StageForecast(
                        stage=stage,
                        actual_days=actual,
                        median_days=actual,
                        historical_median_days=historical,
                        excess_days=actual - historical,
                    )
                )
                continue
            median = float(medians[stage][0])
            forecasts.append(
                StageForecast(
                    stage=stage,
                    actual_days=None,
                    median_days=median,
                    historical_median_days=historical,
                    excess_days=median - historical,
                )
            )
        return tuple(forecasts)

    @staticmethod
    def _cause(
        stages: tuple[StageForecast, ...],
        quantiles: dict[str, np.ndarray],
        features,
    ) -> RiskCause:
        # Chỉ xét chặng CHƯA xong: chặng đã xảy ra thì có chậm cũng không can thiệp
        # được nữa, và nguyên nhân sinh ra là để chọn biện pháp.
        pending = [stage for stage in stages if stage.actual_days is None]
        worst = max(pending, key=lambda forecast: forecast.excess_days)
        seller_id = None
        if STAGE_GRAIN[worst.stage] == "seller":
            medians = quantiles["seller_handling"][:, MEDIAN_INDEX]
            seller_id = str(features.seller_level["seller_id"].iloc[int(medians.argmax())])
        return RiskCause(
            stage=worst.stage, excess_days=worst.excess_days, seller_id=seller_id
        )


def _frames_for(order: OrderInput) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Dựng đúng ba khung mà build_features nhận lúc huấn luyện.

    Đi vòng qua pandas cho một đơn lẻ nghe thừa, nhưng nó bảo đảm đường dự đoán và
    đường huấn luyện chạy qua cùng một đoạn mã đặc trưng. Hai bản sao của cùng một
    phép tính là chỗ sai lệch nảy sinh mà không ai thấy.
    """
    orders = pd.DataFrame(
        [
            {
                "order_id": order.order_id,
                "purchased_at": pd.Timestamp(order.purchased_at),
                "handed_to_carrier_at": pd.Timestamp(order.handed_to_carrier_at),
                "customer_state": order.customer_state,
                "customer_zip": order.customer_zip,
                "estimated_delivery_date": pd.Timestamp(order.estimated_delivery_date),
            }
        ]
    )
    lines = pd.DataFrame(
        [
            {
                "order_id": order.order_id,
                "order_item_id": index + 1,
                "seller_id": line.seller_id,
                "seller_state": line.seller_state,
                "seller_zip": line.seller_zip,
                "product_category_name": line.product_category_name,
                "product_weight_g": line.product_weight_g,
                "price": line.price,
                "freight_value": line.freight_value,
                "shipping_limit_date": pd.NaT,
            }
            for index, line in enumerate(order.lines)
        ]
    )
    payments = pd.DataFrame(
        [
            {
                "order_id": order.order_id,
                "payment_type": payment_type,
                "payment_installments": order.payment_installments,
            }
            for payment_type in order.payment_types
        ]
    )
    return orders, lines, payments


@lru_cache(maxsize=1)
def load_predictor(model_dir: Path) -> RiskPredictor:
    """Bộ nhớ đệm ở mức tiến trình.

    lru_cache không đệm ngoại lệ, nên máy chủ đang chạy mà mô hình được huấn luyện
    xong giữa chừng thì lần gọi kế tiếp nạp được, không phải khởi động lại.

    maxsize=1 hợp với máy chủ thật nhưng làm test phụ thuộc thứ tự chạy: bài trỏ vào
    thư mục này đẩy bài trỏ vào thư mục kia ra khỏi đệm. Test nào đụng RISK_MODEL_DIR
    phải gọi load_predictor.cache_clear() lúc dựng.
    """
    return RiskPredictor.load(model_dir)
