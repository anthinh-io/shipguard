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

### 5.1 Yêu cầu

- **Docker**: Docker Desktop (Windows 10/11, macOS) hoặc Docker Engine kèm Docker Compose (Linux).
- Internet ở lần chạy đầu (tải ảnh nền, cài thư viện), khoảng 8 GB ổ đĩa trống, khuyến nghị RAM 8 GB.
- Ba cổng **3000** (giao diện), **8000** (máy chủ xử lý), **5432** (PostgreSQL) còn trống.
- Không cần cài Python, Node.js hay PostgreSQL. Chỉ cần thêm [uv](https://docs.astral.sh/uv/) nếu trong môi trường phát triển.

### 5.2 Khởi tạo `.env` (nếu chưa có)

Nếu thư mục gốc chưa có tệp `.env`, tạo từ mẫu:

```bash
cp .env.example .env
```

Rồi mở `.env` và điền các giá trị sau, các biến còn lại giữ mặc định:

| Biến | Điền gì |
| --- | --- |
| `POSTGRES_USER`, `POSTGRES_PASSWORD` | Tự chọn; PostgreSQL tạo tài khoản này ở lần chạy đầu |
| `POSTGRES_PORT` | `5432` |
| `JWT_SECRET_KEY` | Chuỗi ngẫu nhiên dài, sinh bằng: `docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD` | Tài khoản Super Admin tạo ở lần chạy đầu, khi chưa có Super Admin nào; mật khẩu tối thiểu 8 ký tự |

`.env` chứa bí mật và đã nằm trong `.gitignore`; không đưa lên Git.

### 5.3 Dữ liệu và mô hình

| Cần có | Dùng để | Nếu chưa có |
| --- | --- | --- |
| `db/initdb/*.sql` (bản dump) | PostgreSQL nạp lược đồ và dữ liệu ở lần chạy đầu | Yêu cầu bản dump `shipguard.sql` và đặt vào `db/initdb/` |
| `models/` | Mô hình rủi ro đã huấn luyện | `uv run python -m app.scripts.train_risk_model` |

Bản dump chỉ được nạp khi volume PostgreSQL còn trống.

### 5.4 Khởi động nhanh hệ thống

Từ thư mục gốc (nơi có `docker-compose.yml`):

```bash
docker compose up -d --build --wait
```

Truy cập trình duyệt tại http://localhost:3000; dịch vụ tại http://localhost:8000 (tài liệu API tại `/docs`).

Lệnh dừng: `docker compose stop`; gỡ và xóa dữ liệu: `docker compose down -v`.

### 5.5 Môi trường phát triển

Từ thư mục gốc (nơi có `docker-compose.yml`):

```bash
cp .env.example .env                                  # rồi điền các giá trị của bạn
docker compose up -d --wait postgres                  # dựng `postgres`, bỏ qua `backend` và `frontend`
uv sync
uv run alembic -c backend/alembic.ini upgrade head    # dựng lược đồ
uv run python -m app.scripts.build_derived_data       # nạp CSV và dựng dẫn xuất
uv run python -m app.scripts.train_risk_model         # huấn luyện mô hình rủi ro
uv run fastapi dev backend/app/main.py                # chạy dịch vụ máy chủ
```

Lệnh huấn luyện đọc thẳng tệp CSV trong `datasets/raw/` nên không phụ thuộc hai bước trước nó và chạy được cả khi Postgres đang tắt.

## 6. Giấy phép

Dự án được thực hiện cho mục đích giáo dục, không sử dụng cho mục đích thương mại.
