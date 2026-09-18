"""Dữ liệu huấn luyện đọc thẳng từ tệp CSV Olist, không qua cơ sở dữ liệu (ADR-0010)."""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.core.config import REPO_ROOT

OLIST_CSV_DIR = REPO_ROOT / "datasets" / "raw"

STAGES = ("payment_approval", "seller_handling", "carrier_transit")

# Sàn một phút. Cần thiết chứ không phải làm đẹp: XGBoost AFT log-normal mô hình hóa
# log(t), nên t = 0 cho -inf và t < 0 không có nghĩa.
MIN_STAGE_DAYS = 1.0 / 1440.0

SECONDS_PER_DAY = 86_400.0


@dataclass(frozen=True)
class TrainingData:
    """Mọi thứ lệnh huấn luyện cần, đã lọc về tập đơn dùng được."""

    orders: pd.DataFrame  # một dòng mỗi đơn, kèm nhãn ba chặng và nhãn trễ
    lines: pd.DataFrame  # một dòng mỗi dòng hàng, đã nối danh mục và người bán
    payments: pd.DataFrame  # một dòng mỗi dòng thanh toán
    zip_coords: pd.DataFrame  # mã bưu chính -> lat, lng
    excluded: dict[str, int]


def _read(csv_dir: Path, name: str, **kwargs) -> pd.DataFrame:
    # utf-8-sig chứ không phải utf-8: product_category_name_translation.csv có BOM, và
    # đọc bằng utf-8 làm tên cột đầu tiên dính ký tự vô hình ở đầu.
    return pd.read_csv(csv_dir / name, encoding="utf-8-sig", **kwargs)


def load_zip_coords(csv_dir: Path = OLIST_CSV_DIR) -> pd.DataFrame:
    """Một toạ độ cho mỗi mã bưu chính — TRUNG VỊ, không phải trung bình cộng.

    Một triệu dòng cho 19.015 mã: mỗi địa chỉ đã định vị là một dòng. Vài chục dòng có
    toạ độ nằm ngoài lãnh thổ Brazil, lỗi định vị đã biết của bộ dữ liệu; trung bình
    cộng bị chúng kéo lệch hàng trăm km còn trung vị thì không.
    """
    geo = _read(
        csv_dir,
        "olist_geolocation_dataset.csv",
        dtype={"geolocation_zip_code_prefix": str},
        usecols=["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng"],
    )
    coords = geo.groupby("geolocation_zip_code_prefix")[
        ["geolocation_lat", "geolocation_lng"]
    ].median()
    coords.index.name = "zip_code_prefix"
    return coords.rename(columns={"geolocation_lat": "lat", "geolocation_lng": "lng"})


def _days(end: pd.Series, start: pd.Series) -> pd.Series:
    return (end - start).dt.total_seconds() / SECONDS_PER_DAY


def load_training_data(
    csv_dir: Path = OLIST_CSV_DIR, *, sample_step: int = 1
) -> TrainingData:
    """Đơn đã giao dùng được, kèm nhãn ba chặng, dòng hàng, thanh toán và bảng toạ độ.

    sample_step > 1 lấy mỗi k đơn một đơn theo thứ tự thời gian. Dùng cho test: giữ
    nguyên khoảng thời gian nên phép chia theo thời điểm đặt vẫn còn nghĩa, khác hẳn
    việc cắt lấy n đơn đầu vốn vứt sạch dữ liệu năm 2018.
    """
    orders = _read(
        csv_dir,
        "olist_orders_dataset.csv",
        parse_dates=[
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    ).rename(
        columns={
            "order_purchase_timestamp": "purchased_at",
            "order_approved_at": "payment_approved_at",
            "order_delivered_carrier_date": "handed_to_carrier_at",
            "order_delivered_customer_date": "delivered_to_customer_at",
            "order_estimated_delivery_date": "estimated_delivery_date",
        }
    )

    delivered = orders[
        (orders["order_status"] == "delivered")
        & orders["delivered_to_customer_at"].notna()
    ]

    # Đếm từng lý do loại riêng để báo cáo nói được vì sao mất đơn, chứ không chỉ còn
    # lại bao nhiêu. Ba điều kiện rời nhau trên dữ liệu Olist: 165 + 23 + 15 = 203.
    missing = (
        delivered["payment_approved_at"].isna() | delivered["handed_to_carrier_at"].isna()
    )
    before_purchase = delivered["handed_to_carrier_at"] < delivered["purchased_at"]
    after_delivery = (
        delivered["handed_to_carrier_at"] > delivered["delivered_to_customer_at"]
    )
    excluded = {
        "delivered": int(len(delivered)),
        "handed_before_purchase": int(before_purchase.sum()),
        "handed_after_delivery": int(after_delivery.sum()),
        "missing_milestone": int(missing.sum()),
    }

    kept = delivered[~missing & ~before_purchase & ~after_delivery].copy()
    excluded["kept"] = int(len(kept))

    # So ở mức NGÀY LỊCH, không so nguyên dấu thời gian: giao đúng ngày cam kết là đúng
    # hạn bất kể mấy giờ. Ngày cam kết trong CSV vốn ở lúc nửa đêm, nên chính phép
    # normalize() bên vế trái mới là thứ tạo ra khác biệt — bỏ nó đi thì nhãn trễ nhảy
    # từ 6.531 lên 7.822 mà không có gì báo. Lớp dẫn xuất đóng cứng phép so này vào cột
    # sinh is_late; ở đây dựng lại bằng tay nên tests/test_risk_dataset.py canh nó.
    kept["is_late"] = kept["delivered_to_customer_at"].dt.normalize() > kept[
        "estimated_delivery_date"
    ].dt.normalize()

    kept["payment_approval"] = _days(kept["payment_approved_at"], kept["purchased_at"])
    kept["seller_handling"] = _days(
        kept["handed_to_carrier_at"], kept["payment_approved_at"]
    )
    kept["carrier_transit"] = _days(
        kept["delivered_to_customer_at"], kept["handed_to_carrier_at"]
    )
    # Kẹp sàn thay vì loại dòng. Hơn một nghìn đơn Olist ghi nhận bàn giao cho đơn vị
    # vận chuyển TRƯỚC khi thanh toán được duyệt, cho ra Seller Handling âm, và hàng
    # nghìn đơn khác có Payment Approval đúng bằng 0. Loại hết chúng là vứt 1,3% dữ
    # liệu vì một đặc thù ghi nhận, nên chúng ở lại và chỉ nhãn bị nâng lên sàn.
    for stage in STAGES:
        kept[stage] = kept[stage].clip(lower=MIN_STAGE_DAYS)

    # Tiebreak bằng order_id: thiếu nó thì hai đơn cùng dấu thời gian đổi chỗ giữa các
    # lần chạy, và mọi thứ tính theo thứ tự — phép chia tập, lịch sử người bán — hết
    # lặp lại được.
    kept = kept.sort_values(["purchased_at", "order_id"], kind="mergesort")
    if sample_step > 1:
        kept = kept.iloc[::sample_step]
    kept = kept.reset_index(drop=True)

    customers = _read(
        csv_dir,
        "olist_customers_dataset.csv",
        dtype={"customer_zip_code_prefix": str},
        usecols=["customer_id", "customer_state", "customer_zip_code_prefix"],
    ).rename(columns={"customer_zip_code_prefix": "customer_zip"})
    orders_out = kept.merge(customers, on="customer_id", how="left")

    order_ids = orders_out[["order_id"]]

    products = _read(
        csv_dir,
        "olist_products_dataset.csv",
        usecols=["product_id", "product_category_name", "product_weight_g"],
    )
    sellers = _read(
        csv_dir,
        "olist_sellers_dataset.csv",
        dtype={"seller_zip_code_prefix": str},
        usecols=["seller_id", "seller_state", "seller_zip_code_prefix"],
    ).rename(columns={"seller_zip_code_prefix": "seller_zip"})
    # drop_duplicates: tệp người bán có những dòng lặp y hệt, và để nguyên thì phép nối
    # dưới đây nhân đôi dòng hàng trong im lặng.
    sellers = sellers.drop_duplicates(subset="seller_id")

    lines = (
        _read(
            csv_dir,
            "olist_order_items_dataset.csv",
            parse_dates=["shipping_limit_date"],
        )
        .merge(order_ids, on="order_id")
        .merge(products, on="product_id", how="left")
        .merge(sellers, on="seller_id", how="left")
    )

    payments = _read(csv_dir, "olist_order_payments_dataset.csv").merge(
        order_ids, on="order_id"
    )

    return TrainingData(
        orders=orders_out,
        lines=lines,
        payments=payments,
        zip_coords=load_zip_coords(csv_dir),
        excluded=excluded,
    )


def split_by_purchase_time(
    orders: pd.DataFrame,
    *,
    train_ratio: float = 0.70,
    validation_ratio: float = 0.15,
) -> dict[str, pd.DataFrame]:
    """Chia theo thời điểm đặt hàng (mặc định 70/15/15), không trộn ngẫu nhiên.

    Trộn ngẫu nhiên cho điểm đánh giá đẹp hơn nhiều nhưng là giả: mô hình thật luôn
    dự đoán cho đơn đặt SAU mọi đơn nó đã học. Tỷ lệ trễ của Olist tụt từ 7,8% xuống
    4,3% giữa đầu và cuối dữ liệu, nên đây là chỗ khác biệt lớn chứ không hình thức.
    """
    ordered = orders.sort_values(["purchased_at", "order_id"], kind="mergesort")
    total = len(ordered)
    train_end = int(total * train_ratio)
    validation_end = train_end + int(total * validation_ratio)
    return {
        "train": ordered.iloc[:train_end].reset_index(drop=True),
        "validation": ordered.iloc[train_end:validation_end].reset_index(drop=True),
        "test": ordered.iloc[validation_end:].reset_index(drop=True),
    }
