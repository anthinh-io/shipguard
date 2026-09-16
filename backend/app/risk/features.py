"""Đặc trưng cho ba mô hình chặng, dùng chung một lược đồ cột.

Hai mức hạt: một dòng mỗi đơn cho `Payment Approval` và `Carrier Transit`, một dòng
mỗi (đơn, người bán) cho `Seller Handling` — vì đơn chờ người bán chậm nhất.

Cùng bộ hàm phục vụ cả lúc huấn luyện lẫn lúc dự đoán. Khác biệt duy nhất là lịch sử
người bán: huấn luyện tính bằng cửa sổ giãn dần chỉ nhìn về quá khứ, còn dự đoán nhận
sẵn bảng thống kê trên toàn bộ dữ liệu Olist.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

CATEGORICAL_FEATURES = (
    "customer_state",
    "seller_state",
    "route",
    "category",
    "payment_type_combo",
)

NUMERIC_FEATURES = (
    "distance_km",
    "total_weight_g",
    "total_price",
    "total_freight",
    "line_count",
    "seller_count",
    "max_installments",
    "purchase_month",
    "purchase_weekday",
    "purchase_hour",
    "commitment_days",
    "seller_prior_orders",
    "seller_prior_handling_days",
    "seller_prior_late_rate",
    "seller_prior_overdue_handoff_rate",
)

FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES

HISTORY_COLUMNS = (
    "seller_prior_orders",
    "seller_prior_handling_days",
    "seller_prior_late_rate",
    "seller_prior_overdue_handoff_rate",
)

# Chặng nào đọc khung nào. `Seller Handling` dự đoán cho từng người bán vì đơn chờ
# người chậm nhất; hai chặng kia ở mức đơn. Một bảng tra dùng chung cho cả lúc huấn
# luyện lẫn lúc dự đoán — viết tay điều kiện này ở mỗi nơi cần là cách để hai nơi lệch
# nhau về sau.
STAGE_GRAIN = {
    "payment_approval": "order",
    "seller_handling": "seller",
    "carrier_transit": "order",
}

EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class Features:
    order_level: pd.DataFrame  # một dòng mỗi đơn
    seller_level: pd.DataFrame  # một dòng mỗi (đơn, người bán)


def haversine_km(
    lat1: pd.Series, lng1: pd.Series, lat2: pd.Series, lng2: pd.Series
) -> np.ndarray:
    """Khoảng cách vòng lớn giữa hai điểm, tính bằng km. Thiếu toạ độ thì ra NaN."""
    lat1, lng1, lat2, lng2 = (
        np.radians(np.asarray(value, dtype=float)) for value in (lat1, lng1, lat2, lng2)
    )
    inner = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(inner))


def _attach_coords(
    frame: pd.DataFrame, zip_coords: pd.DataFrame, zip_column: str, prefix: str
) -> pd.DataFrame:
    renamed = zip_coords.rename(columns={"lat": f"{prefix}_lat", "lng": f"{prefix}_lng"})
    return frame.merge(
        renamed, left_on=zip_column, right_index=True, how="left", validate="m:1"
    )


def _prior_mean(frame: pd.DataFrame, column: str, counts: pd.Series) -> pd.Series:
    """Trung bình của các giá trị đứng TRƯỚC dòng hiện tại, trong cùng một người bán.

    Trừ đi chính giá trị của dòng hiện tại khỏi tổng tích luỹ là cách chặn rò rỉ thời
    gian ở đây. Thiếu bước trừ đó, đặc trưng của một đơn có chính đơn đó trong mẫu —
    mô hình biết trước kết quả nó phải dự đoán, điểm đánh giá đẹp lên và mô hình thật
    thì tệ đi. Không có gì trong giao diện làm lộ ra chuyện này.

    Viết bằng cumsum thay vì groupby.transform(lambda): cùng kết quả, nhưng một lượt
    quét thay vì ba nghìn lượt gọi hàm Python.
    """
    values = frame[column].astype(float)
    prior_sum = values.groupby(frame["seller_id"], sort=False).cumsum() - values
    return prior_sum / counts.where(counts > 0)


def add_seller_history(seller_orders: pd.DataFrame) -> pd.DataFrame:
    """Bốn đặc trưng lịch sử, chỉ tính trên các đơn người bán đó nhận TRƯỚC đơn đang xét.

    Sắp xếp theo (purchased_at, order_id, seller_id): thiếu tiebreak thì hai đơn cùng
    dấu thời gian đổi chỗ giữa các lần chạy và đặc trưng hết lặp lại được.
    """
    ordered = seller_orders.sort_values(
        ["purchased_at", "order_id", "seller_id"], kind="mergesort"
    )
    counts = ordered.groupby("seller_id", sort=False).cumcount()

    ordered["seller_prior_orders"] = counts
    ordered["seller_prior_handling_days"] = _prior_mean(
        ordered, "seller_handling", counts
    )
    ordered["seller_prior_late_rate"] = _prior_mean(ordered, "is_late", counts)
    ordered["seller_prior_overdue_handoff_rate"] = _prior_mean(
        ordered, "overdue_handoff", counts
    )
    return ordered


def seller_history_snapshot(seller_orders: pd.DataFrame) -> pd.DataFrame:
    """Thống kê người bán trên TOÀN BỘ dữ liệu, để dùng lúc dự đoán cho đơn mới.

    Không rò rỉ gì: một đơn tạo trong Ship Guard luôn đứng sau mọi đơn Olist, nên
    "toàn bộ quá khứ" và "toàn bộ dữ liệu" là một.
    """
    grouped = seller_orders.groupby("seller_id")
    return pd.DataFrame(
        {
            "seller_prior_orders": grouped.size(),
            "seller_prior_handling_days": grouped["seller_handling"].mean(),
            "seller_prior_late_rate": grouped["is_late"].mean(),
            "seller_prior_overdue_handoff_rate": grouped["overdue_handoff"].mean(),
        }
    )


def build_seller_orders(
    orders: pd.DataFrame, lines: pd.DataFrame, zip_coords: pd.DataFrame
) -> pd.DataFrame:
    """Gộp dòng hàng về một dòng mỗi (đơn, người bán), kèm toạ độ và cờ quá hạn bàn giao."""
    order_columns = [
        "order_id",
        "purchased_at",
        "handed_to_carrier_at",
        "customer_state",
        "customer_zip",
        "estimated_delivery_date",
    ]
    optional = [column for column in ("is_late", "seller_handling") if column in orders]
    merged = lines.merge(orders[order_columns + optional], on="order_id")

    merged["line_value"] = merged["price"] + merged["freight_value"]
    merged["overdue_handoff"] = (
        merged["handed_to_carrier_at"] > merged["shipping_limit_date"]
    ).astype(float)

    grouped = merged.groupby(["order_id", "seller_id"], as_index=False).agg(
        seller_state=("seller_state", "first"),
        seller_zip=("seller_zip", "first"),
        line_count=("order_item_id", "size"),
        total_price=("price", "sum"),
        total_freight=("freight_value", "sum"),
        total_weight_g=("product_weight_g", "sum"),
        line_value=("line_value", "sum"),
        overdue_handoff=("overdue_handoff", "max"),
    )

    # Danh mục đại diện là danh mục của dòng hàng đắt nhất, tiebreak bằng thứ tự dòng
    # để hai lần chạy cho cùng một kết quả.
    top_line = merged.sort_values(
        ["line_value", "order_item_id"], ascending=[False, True], kind="mergesort"
    ).drop_duplicates(["order_id", "seller_id"])
    grouped = grouped.merge(
        top_line[["order_id", "seller_id", "product_category_name"]].rename(
            columns={"product_category_name": "category"}
        ),
        on=["order_id", "seller_id"],
        how="left",
    )

    grouped = grouped.merge(orders[order_columns + optional], on="order_id")
    grouped = _attach_coords(grouped, zip_coords, "seller_zip", "seller")
    grouped = _attach_coords(grouped, zip_coords, "customer_zip", "customer")
    grouped["distance_km"] = haversine_km(
        grouped["seller_lat"],
        grouped["seller_lng"],
        grouped["customer_lat"],
        grouped["customer_lng"],
    )
    return grouped


def _payment_summary(payments: pd.DataFrame) -> pd.DataFrame:
    distinct = payments[["order_id", "payment_type"]].drop_duplicates().sort_values(
        ["order_id", "payment_type"], kind="mergesort"
    )
    combo = distinct.groupby("order_id")["payment_type"].agg("+".join)
    return pd.DataFrame(
        {
            "payment_type_combo": combo,
            "max_installments": payments.groupby("order_id")["payment_installments"].max(),
        }
    )


def _shared_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["route"] = frame["seller_state"].astype(str) + "→" + frame["customer_state"].astype(str)
    purchased = frame["purchased_at"]
    frame["purchase_month"] = purchased.dt.month
    frame["purchase_weekday"] = purchased.dt.weekday
    frame["purchase_hour"] = purchased.dt.hour
    frame["commitment_days"] = (
        frame["estimated_delivery_date"].dt.normalize() - purchased.dt.normalize()
    ).dt.days
    return frame


def build_features(
    orders: pd.DataFrame,
    lines: pd.DataFrame,
    payments: pd.DataFrame,
    zip_coords: pd.DataFrame,
    *,
    history: pd.DataFrame | None = None,
) -> Features:
    """Hai khung đặc trưng dùng chung lược đồ cột.

    history là None lúc huấn luyện — lịch sử được tính bằng cửa sổ giãn dần chỉ nhìn
    quá khứ. Lúc dự đoán, truyền vào bảng thống kê đi kèm tệp mô hình.
    """
    payment_summary = _payment_summary(payments)
    seller_orders = build_seller_orders(orders, lines, zip_coords)

    if history is None:
        seller_orders = add_seller_history(seller_orders)
    else:
        seller_orders = seller_orders.merge(
            history, left_on="seller_id", right_index=True, how="left", validate="m:1"
        )
        for column in HISTORY_COLUMNS:
            if column not in seller_orders:
                seller_orders[column] = np.nan

    seller_counts = seller_orders.groupby("order_id")["seller_id"].transform("size")
    seller_orders["seller_count"] = seller_counts
    seller_level = _shared_columns(seller_orders)

    # Đại diện của đơn là người bán có giá trị dòng hàng lớn nhất; tiebreak bằng mã
    # người bán. Với 1,3% đơn nhiều người bán, hàng hoá xuất phát từ nhiều nơi và
    # chỉ chọn được một điểm đi — đây là giả định, không phải kết quả đo.
    dominant = seller_level.sort_values(
        ["line_value", "seller_id"], ascending=[False, True], kind="mergesort"
    ).drop_duplicates("order_id")

    # Lịch sử ở mức đơn lấy giá trị xấu nhất trong các người bán: đơn chờ người chậm
    # nhất. seller_prior_orders lấy giá trị nhỏ nhất vì ít đơn trước là ít hiểu biết,
    # không phải nhiều. Ba giá trị có thể đến từ ba người bán khác nhau — chấp nhận
    # được ở mức 1,3% đơn.
    worst = seller_level.groupby("order_id").agg(
        seller_prior_orders=("seller_prior_orders", "min"),
        seller_prior_handling_days=("seller_prior_handling_days", "max"),
        seller_prior_late_rate=("seller_prior_late_rate", "max"),
        seller_prior_overdue_handoff_rate=("seller_prior_overdue_handoff_rate", "max"),
        total_price=("total_price", "sum"),
        total_freight=("total_freight", "sum"),
        total_weight_g=("total_weight_g", "sum"),
        line_count=("line_count", "sum"),
    )

    order_level = (
        dominant.drop(columns=list(worst.columns))
        .merge(worst, left_on="order_id", right_index=True)
        .merge(payment_summary, left_on="order_id", right_index=True, how="left")
    )
    # Khung mức người bán cũng cần thông tin thanh toán: thanh toán chưa duyệt là một
    # lý do người bán chưa gửi hàng.
    seller_level = seller_level.merge(
        payment_summary, left_on="order_id", right_index=True, how="left"
    )

    return Features(
        order_level=order_level.sort_values("order_id").reset_index(drop=True),
        seller_level=seller_level.sort_values(["order_id", "seller_id"]).reset_index(
            drop=True
        ),
    )
