"""Huấn luyện ba bộ ứng viên, đánh giá theo mốc dự đoán, chọn một bộ và xuất báo cáo."""

import csv
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from app.risk.candidates import ALGORITHMS, QUANTILES, FeatureEncoder, StageModel
from app.risk.dataset import (
    STAGES,
    TrainingData,
    load_training_data,
    split_by_purchase_time,
)
from app.risk.features import (
    FEATURES,
    STAGE_GRAIN,
    build_features,
    build_seller_orders,
    seller_history_snapshot,
)
from app.risk.predictor import (
    CHECKPOINTS,
    MODEL_FILENAME,
    SETTLED_AT_CHECKPOINT,
    ModelBundle,
    deadline_days,
    rng_for,
    simulate,
)

F1_TARGET = 0.30

REPORT_FILENAME = "evaluation_report.json"
METRICS_FILENAME = "evaluation_metrics.csv"
PREDICTIONS_FILENAME = "test_predictions.csv"

# Quét từ 0,01 đến 0,99. Không có 0 và 1 vì hai đầu vô nghĩa: 0 là gắn cờ mọi đơn,
# 1 là không đơn nào.
THRESHOLD_GRID = np.round(np.arange(0.01, 1.00, 0.01), 2)

# Mô phỏng theo lô đơn để không cấp phát cả mảng (đơn × mẫu) cùng lúc: 14.430 đơn ×
# 2.000 mẫu là 231 MB cho mỗi chặng.
CHUNK_ORDERS = 2_000

@dataclass(frozen=True)
class Split:
    name: str
    orders: pd.DataFrame
    sellers: pd.DataFrame
    order_codes: np.ndarray
    deadline: np.ndarray
    is_late: np.ndarray


def metrics_at(probabilities: np.ndarray, truth: np.ndarray, threshold: float) -> dict:
    flagged = probabilities >= threshold
    true_positive = int(np.sum(flagged & truth))
    false_positive = int(np.sum(flagged & ~truth))
    false_negative = int(np.sum(~flagged & truth))
    true_negative = int(np.sum(~flagged & ~truth))
    total = true_positive + false_positive + false_negative + true_negative

    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 0.0
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 0.0
    )
    f1 = (
        2 * precision * recall / (precision + recall) if precision + recall else 0.0
    )
    accuracy = (true_positive + true_negative) / total if total else 0.0
    return {
        "threshold": round(float(threshold), 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
    }


def roc_auc(probabilities: np.ndarray, truth: np.ndarray) -> float | None:
    """None khi tập chỉ có một lớp nhãn — ROC-AUC không định nghĩa được, không phải lỗi."""
    if len(np.unique(truth)) < 2:
        return None
    return round(float(roc_auc_score(truth, probabilities)), 4)


def sweep_thresholds(probabilities: np.ndarray, truth: np.ndarray) -> dict:
    """Ngưỡng cho F1 cao nhất. Hoà thì lấy ngưỡng NHỎ NHẤT.

    Quy tắc hoà không phải trang trí: trên một tập nhỏ mọi ngưỡng có thể cùng cho F1
    bằng 0, và không định nghĩa trước thì "ngưỡng đề xuất" thành một giá trị tuỳ tiện
    hoặc không tồn tại. argmax trả về vị trí đầu tiên, tức ngưỡng nhỏ nhất.
    """
    scored = [metrics_at(probabilities, truth, threshold) for threshold in THRESHOLD_GRID]
    best = int(np.argmax([entry["f1"] for entry in scored]))
    return scored[best]


def _build_splits(
    data: TrainingData, *, train_ratio: float, validation_ratio: float
) -> dict[str, Split]:
    features = build_features(data.orders, data.lines, data.payments, data.zip_coords)

    # Bỏ các cột nhãn mà tầng đặc trưng mang theo rồi nối lại toàn bộ nhãn một lượt:
    # nối đè lên nhau sinh ra hậu tố _x/_y và một cột nhãn câm không ai để ý.
    labels = data.orders[["order_id", *STAGES, "is_late"]]
    drop = ["is_late", "seller_handling"]
    order_level = features.order_level.drop(columns=drop, errors="ignore").merge(
        labels, on="order_id"
    )
    seller_level = features.seller_level.drop(columns=drop, errors="ignore").merge(
        labels, on="order_id"
    )

    splits = {}
    for name, part in split_by_purchase_time(
        data.orders, train_ratio=train_ratio, validation_ratio=validation_ratio
    ).items():
        keep = set(part["order_id"])
        orders = order_level[order_level["order_id"].isin(keep)].sort_values("order_id")
        orders = orders.reset_index(drop=True)
        sellers = (
            seller_level[seller_level["order_id"].isin(keep)]
            .sort_values(["order_id", "seller_id"])
            .reset_index(drop=True)
        )
        # Mã số thứ tự đơn cho từng dòng người bán; _max_within_order dựa vào việc các
        # dòng cùng đơn nằm liền nhau, nên thứ tự sắp xếp ở trên là bắt buộc.
        codes = pd.Index(orders["order_id"]).get_indexer(sellers["order_id"])
        splits[name] = Split(
            name=name,
            orders=orders,
            sellers=sellers,
            order_codes=codes,
            deadline=deadline_days(
                orders["purchased_at"], orders["estimated_delivery_date"]
            ),
            is_late=orders["is_late"].to_numpy(dtype=bool),
        )
    return splits


def _fit_models(
    encoder: FeatureEncoder, factory: Callable[[], StageModel], train: Split
) -> dict:
    models = {}
    for stage in STAGES:
        frame = train.orders if STAGE_GRAIN[stage] == "order" else train.sellers
        model = factory()
        model.fit(encoder.transform(frame), frame[stage].to_numpy(dtype=float))
        models[stage] = model
    return models


def _probabilities(models: dict, encoder: FeatureEncoder, split: Split, checkpoint: str):
    """Xác suất trễ của cả tập tại một mốc, chạy theo lô đơn."""
    settled_stages = SETTLED_AT_CHECKPOINT[checkpoint]
    pending = [stage for stage in STAGES if stage not in settled_stages]

    grids = {
        stage: models[stage].predict_quantiles(
            encoder.transform(
                split.orders if STAGE_GRAIN[stage] == "order" else split.sellers
            )
        )
        for stage in pending
    }

    chunks = []
    for start in range(0, len(split.orders), CHUNK_ORDERS):
        stop = min(start + CHUNK_ORDERS, len(split.orders))
        rows = np.flatnonzero((split.order_codes >= start) & (split.order_codes < stop))
        chunk_grids = {
            stage: grids[stage][rows] if STAGE_GRAIN[stage] == "seller" else grids[stage][start:stop]
            for stage in pending
        }
        settled = {
            stage: split.orders[stage].to_numpy(dtype=float)[start:stop]
            for stage in settled_stages
        }
        # Hạt giống bám theo (mốc, vị trí lô) nên hai lần chạy cho cùng kết quả. Đường
        # dự đoán thật gieo theo mã đơn; ở đây gieo theo lô để mô phỏng cả tập một
        # lượt. Khác nhau ở bộ số ngẫu nhiên được dùng, không ở phép ước lượng.
        probability, _ = simulate(
            quantiles=chunk_grids,
            settled=settled,
            order_codes=split.order_codes[rows] - start,
            order_count=stop - start,
            deadline=split.deadline[start:stop],
            generator=rng_for(f"{split.name}:{checkpoint}:{start}"),
        )
        chunks.append(probability)
    return np.concatenate(chunks)


def _evaluate(models: dict, encoder: FeatureEncoder, splits: dict) -> tuple[dict, dict]:
    report: dict[str, Any] = {}
    predictions: dict[str, np.ndarray] = {}

    for split_name in ("validation", "test"):
        report[split_name] = {}
        for checkpoint in CHECKPOINTS:
            split = splits[split_name]
            probability = _probabilities(models, encoder, split, checkpoint)
            scored = sweep_thresholds(probability, split.is_late)
            scored["roc_auc"] = roc_auc(probability, split.is_late)
            report[split_name][checkpoint] = scored
            if split_name == "test":
                predictions[checkpoint] = probability
    return report, predictions


def _apply_chosen_threshold(report: dict, threshold: float, predictions: dict, splits):
    """Thêm con số thật sự nhận được khi triển khai, cạnh con số tốt nhất của phép quét.

    Ngưỡng của mỗi thuật toán lấy từ chính tập kiểm định của nó, không phải ngưỡng của
    bộ được chọn áp cho cả ba — làm thế thì hai thuật toán kia bị chấm bằng thước của
    người khác.
    """
    truth = splits["test"].is_late
    for checkpoint in CHECKPOINTS:
        entry = report["test"][checkpoint]
        entry["best_f1"] = entry.pop("f1")
        entry["best_threshold"] = entry.pop("threshold")
        entry["at_selected_threshold"] = metrics_at(
            predictions[checkpoint], truth, threshold
        )


def train(
    model_dir: Path,
    *,
    sample_step: int = 1,
    algorithms: Mapping[str, Callable[[], StageModel]] = ALGORITHMS,
    train_ratio: float = 0.70,
    validation_ratio: float = 0.15,
) -> dict[str, Any]:
    data = load_training_data(sample_step=sample_step)
    splits = _build_splits(data, train_ratio=train_ratio, validation_ratio=validation_ratio)

    encoder = FeatureEncoder().fit(splits["train"].orders)

    evaluations: dict[str, Any] = {}
    fitted: dict[str, dict] = {}
    test_predictions: dict[str, dict] = {}

    for name, factory in algorithms.items():
        models = _fit_models(encoder, factory, splits["train"])
        evaluation, predictions = _evaluate(models, encoder, splits)

        threshold = evaluation["validation"]["order_placed"]["threshold"]
        _apply_chosen_threshold(evaluation, threshold, predictions, splits)

        evaluations[name] = evaluation
        fitted[name] = models
        test_predictions[name] = predictions

    # Chọn theo F1 cao nhất ở mốc ĐẶT HÀNG trên tập KIỂM TRA, ngưỡng lấy từ tập KIỂM
    # ĐỊNH (ADR-0008). Phản xạ quen thuộc là chọn cả hai trên kiểm định; ở đây khác đi
    # có chủ đích, và mốc đặt hàng là mốc khó nhất đồng thời là lúc can thiệp còn giá
    # trị nhất.
    selected = max(
        evaluations, key=lambda name: evaluations[name]["test"]["order_placed"]["best_f1"]
    )
    suggested_threshold = evaluations[selected]["validation"]["order_placed"]["threshold"]
    achieved = evaluations[selected]["test"]["order_placed"]["at_selected_threshold"]["f1"]

    model_version = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    # Ảnh chụp lịch sử người bán trên TOÀN BỘ dữ liệu, khác hẳn cửa sổ giãn dần dùng
    # lúc huấn luyện: đơn mới luôn đứng sau mọi đơn Olist nên không có gì để rò rỉ.
    seller_orders = build_seller_orders(data.orders, data.lines, data.zip_coords)

    report = {
        "model_version": model_version,
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "data_source": "datasets/raw (CSV)",
        "sample_step": sample_step,
        "selected_algorithm": selected,
        "suggested_risk_threshold": suggested_threshold,
        "f1_target": F1_TARGET,
        "meets_f1_target": achieved >= F1_TARGET,
        "f1_at_order_placed": achieved,
        "selection_rule": "F1 cao nhất ở mốc order_placed trên tập test",
        "threshold_rule": (
            "ngưỡng cho F1 cao nhất ở mốc order_placed trên tập validation"
        ),
        "monte_carlo_note": (
            "Đánh giá mô phỏng theo lô nên bộ số ngẫu nhiên khác đường dự đoán thật, "
            "vốn gieo theo mã đơn. Phép ước lượng là một."
        ),
        "features": list(FEATURES),
        "quantiles": list(QUANTILES),
        "historical_median_days": {
            stage: float(data.orders[stage].median()) for stage in STAGES
        },
        "splits": {
            name: {
                "rows": int(len(split.orders)),
                "late_rate": round(float(split.is_late.mean()), 4),
                "from": str(split.orders["purchased_at"].min().date()),
                "to": str(split.orders["purchased_at"].max().date()),
            }
            for name, split in splits.items()
        },
        "excluded_orders": data.excluded,
        "algorithms": evaluations,
    }

    bundle = ModelBundle(
        model_version=model_version,
        algorithm=selected,
        encoder=encoder,
        stage_models=fitted[selected],
        historical_median_days=report["historical_median_days"],
        seller_history=seller_history_snapshot(seller_orders),
        zip_coords=data.zip_coords,
    )

    _write_outputs(
        model_dir, bundle, report, splits["test"], test_predictions[selected]
    )
    return report


def _write_outputs(
    model_dir: Path,
    bundle: ModelBundle,
    report: dict,
    test_split: Split,
    predictions: dict,
) -> None:
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(bundle, model_dir / MODEL_FILENAME)
    (model_dir / REPORT_FILENAME).write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    with open(model_dir / METRICS_FILENAME, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["algorithm", "checkpoint", "precision", "recall", "f1", "accuracy", "roc_auc"]
        )
        for algorithm, evaluation in report["algorithms"].items():
            for checkpoint in CHECKPOINTS:
                chosen = evaluation["test"][checkpoint]["at_selected_threshold"]
                writer.writerow(
                    [
                        algorithm,
                        checkpoint,
                        chosen["precision"],
                        chosen["recall"],
                        chosen["f1"],
                        chosen["accuracy"],
                        evaluation["test"][checkpoint]["roc_auc"],
                    ]
                )

    frame = pd.concat(
        [
            pd.DataFrame(
                {
                    "order_id": test_split.orders["order_id"],
                    "checkpoint": checkpoint,
                    "late_probability": probability,
                    "is_late": test_split.is_late,
                }
            )
            for checkpoint, probability in predictions.items()
        ]
    )
    frame.to_csv(model_dir / PREDICTIONS_FILENAME, index=False)


def format_summary(report: dict) -> str:
    """Bảng tóm tắt in ra terminal — nhìn là biết điền gì vào RISK_THRESHOLD."""
    lines = [
        f"Phiên bản mô hình: {report['model_version']}",
        f"Thuật toán được chọn: {report['selected_algorithm']}",
        "",
        f"{'':<20}{'order_placed':>14}{'payment_approved':>18}{'handed_to_carrier':>19}",
    ]
    for algorithm, evaluation in report["algorithms"].items():
        scores = "".join(
            f"{evaluation['test'][checkpoint]['at_selected_threshold']['f1']:>{width}.2f}"
            for checkpoint, width in zip(CHECKPOINTS, (14, 18, 19))
        )
        marker = "  <- được chọn" if algorithm == report["selected_algorithm"] else ""
        lines.append(f"{algorithm:<20}{scores}{marker}")
    selected_best = report["algorithms"][report["selected_algorithm"]]["test"][
        "order_placed"
    ]["best_f1"]
    lines += [
        "  (F1 trên tập kiểm tra, mỗi thuật toán tại ngưỡng riêng lấy từ tập kiểm định)",
        "",
        # Bảng trên có thể cho thấy một thuật toán khác điểm cao hơn. Không mâu thuẫn:
        # ADR-0008 chốt chọn theo F1 TỐT NHẤT của phép quét ngưỡng trên tập kiểm tra,
        # còn bảng trên là điểm tại ngưỡng lấy từ tập kiểm định. Nói rõ ở đây để người
        # đọc không phải đoán vì sao.
        f"Chọn theo F1 tốt nhất của phép quét ở mốc đặt hàng trên tập kiểm tra: "
        f"{selected_best:.2f}",
        "",
        f"Ngưỡng đề xuất: {report['suggested_risk_threshold']}"
        f"    ->  đặt RISK_THRESHOLD={report['suggested_risk_threshold']} trong .env",
    ]
    selected_at_order_placed = report["algorithms"][report["selected_algorithm"]][
        "test"
    ]["order_placed"]
    accuracy = selected_at_order_placed["at_selected_threshold"]["accuracy"]
    roc = selected_at_order_placed["roc_auc"]
    roc_text = f"{roc:.2f}" if roc is not None else "không tính được (một lớp nhãn)"
    lines.append(
        f"Accuracy tại ngưỡng đề xuất: {accuracy:.2f}    ROC-AUC (mốc đặt hàng): {roc_text}"
    )
    verdict = "ĐẠT" if report["meets_f1_target"] else "CHƯA ĐẠT"
    lines.append(
        f"Mục tiêu F1 >= {report['f1_target']:.2f} ở mốc đặt hàng: "
        f"{verdict} ({report['f1_at_order_placed']:.2f})"
    )
    return "\n".join(lines)
