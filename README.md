# ShipGuard: Delivery Performance Intelligence

**Ứng dụng quản lý và dự đoán hiệu suất giao hàng bằng học máy**

Dự án giải quyết bài toán thiếu công cụ dữ liệu có hệ thống để giám sát hiệu suất giao hàng và dự đoán rủi ro giao trễ trong lĩnh vực hậu cần và quản lý chuỗi cung ứng.

## 1. Tổng quan

Hệ thống gồm hai thành phần song song, kết nối qua giao diện lập trình ứng dụng (API) dạng REST:

- **Bảng điều khiển vận hành** — theo dõi chỉ số hiệu suất chính (KPI), quản lý đơn hàng, trực quan hóa xu hướng giao hàng.
- **Giao diện lập trình ứng dụng** — phân loại rủi ro giao hàng (đúng hạn / trễ) bằng mô hình huấn luyện trên bộ dữ liệu [Olist Brazilian E-Commerce](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (~100.000 đơn hàng).

Người dùng nhập thông tin đơn hàng và nhận dự đoán rủi ro giao trễ theo thời gian thực ngay trên giao diện.

## 2. Công nghệ sử dụng

| Tầng | Công nghệ |
| --- | --- |
| Giao diện người dùng | React / Next.js |
| Hệ thống phía máy chủ | FastAPI |
| Cơ sở dữ liệu | PostgreSQL (Docker Compose), lược đồ quản lý bằng Alembic |
| Mô hình học máy | Scikit-learn, XGBoost |
| Xử lý dữ liệu | Pandas, NumPy |
| Trực quan hóa dữ liệu | Recharts |
| Bộ dữ liệu | Olist Brazilian E-Commerce (Kaggle) |

## 3. Kết quả kỳ vọng

- Ứng dụng hoạt động hoàn chỉnh, thay thế quy trình quản lý hậu cần thủ công.
- Mô hình học máy đạt điểm F1 ≥ 0.30 trên bài toán phân loại giao trễ.
- Giao diện ứng dụng cho phép dự đoán thời gian thực từ trình duyệt.
- Nền tảng mở rộng: tối ưu tuyến đường, trợ lý trí tuệ nhân tạo, hệ thống quản lý chuỗi cung ứng đầy đủ.

## 4. Lộ trình

- [ ] **Giai đoạn 1** — Phân tích & khám phá dữ liệu
- [ ] **Giai đoạn 2** — Xây dựng mô hình học máy
- [ ] **Giai đoạn 3** — Xây giao diện ứng dụng
- [ ] **Giai đoạn 4** — Kiểm thử & hoàn thiện

## 5. Cài đặt

Thứ tự bắt buộc, chạy từ gốc repo — mỗi bước cần bước trước đã xong:

```bash
cp .env.example .env                                  # rồi điền các giá trị của bạn
docker compose up -d --wait postgres
uv sync
uv run alembic -c backend/alembic.ini upgrade head    # dựng lược đồ
uv run python -m app.scripts.load_raw_data            # nạp thô
uv run python -m app.scripts.build_derived_data       # dựng dẫn xuất
uv run python -m app.scripts.train_risk_model         # huấn luyện mô hình rủi ro
uv run fastapi dev backend/app/main.py                # chạy backend
```

Lệnh huấn luyện đọc thẳng tệp CSV trong `datasets/raw/` nên không phụ thuộc ba bước trước nó và chạy được cả khi Postgres đang tắt; xếp ở đây vì backend cần tệp mô hình thì mới dự đoán được. Nó in ra một "Ngưỡng đề xuất" — chép con số đó vào `RISK_THRESHOLD` trong `.env`.

Chi tiết cấu hình, biến môi trường và cách đọc báo cáo đánh giá: [backend/README.md](backend/README.md).

## 6. Giấy phép

Dự án được thực hiện cho mục đích giáo dục, không sử dụng cho mục đích thương mại.
