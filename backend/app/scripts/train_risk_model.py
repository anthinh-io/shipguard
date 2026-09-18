import sys

from app.core.config import settings
from app.risk.training import REPORT_FILENAME, format_summary, train


def main() -> None:
    # Bảng tóm tắt viết bằng tiếng Việt, còn console Windows mặc định là cp1252 và
    # dừng hẳn với UnicodeEncodeError ở chữ có dấu đầu tiên. Đặt lại mã hoá ở đây chứ
    # không bắt người chạy phải tự đặt PYTHONIOENCODING.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    report = train(model_dir=settings.RISK_MODEL_DIR)

    print(format_summary(report))
    print()
    print(f"Đã ghi vào {settings.RISK_MODEL_DIR}; báo cáo đầy đủ ở {REPORT_FILENAME}.")


if __name__ == "__main__":
    main()
