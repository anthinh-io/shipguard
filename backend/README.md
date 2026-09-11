# ShipGuard: Delivery Performance Intelligence — Backend

Máy chủ FastAPI và cơ sở dữ liệu PostgreSQL cho hệ thống giám sát hiệu suất giao hàng.

## Yêu cầu

- Docker (kèm Docker Compose)
- [uv](https://docs.astral.sh/uv/) — tự tải Python 3.12 về, không cần cài Python sẵn

Toàn bộ lệnh dưới đây chạy **từ gốc repo**. Dự án dùng uv workspace: một môi
trường ảo duy nhất ở gốc, `backend/` là một thành viên.

## Cấu trúc

```
backend/
  app/
    main.py        khởi tạo FastAPI, gắn router
    core/          cấu hình và kết nối cơ sở dữ liệu
      config.py    đọc .env ở gốc repo
      db.py        engine, session, lớp Base của model
    api/
      deps.py      SessionDep — phụ thuộc session dùng chung cho mọi endpoint
      routes/      mỗi tệp một nhóm endpoint
    alembic/       migration
  tests/
  alembic.ini
  pyproject.toml   phụ thuộc riêng của backend
```

Bố cục theo `fastapi/full-stack-fastapi-template`.

## Khởi động

Chép tệp môi trường rồi điền `POSTGRES_USER` và `POSTGRES_PASSWORD` của bạn:

```bash
cp .env.example .env
```

Dựng cơ sở dữ liệu, cài phụ thuộc, chạy migration, khởi động máy chủ:

```bash
docker compose up -d --wait postgres
uv sync
uv run alembic -c backend/alembic.ini upgrade head
uv run python -m app.scripts.load_raw_data
uv run python -m app.scripts.build_derived_data
uv run fastapi dev backend/app/main.py
```

`--wait` chặn cho tới khi Postgres nhận kết nối. Thiếu nó thì lệnh migration
ngay sau đó có thể chạy trong lúc cơ sở dữ liệu còn đang khởi tạo và bị từ chối.

Lệnh `load_raw_data` nạp 9 tệp CSV Olist trong `datasets/raw/` vào các bảng
`raw_*`, nguyên trạng không lọc hay biến đổi. Chạy lại an toàn: mỗi bảng được
xoá sạch (`TRUNCATE`) rồi nạp lại trong cùng một transaction trước khi nạp,
nên không bao giờ bị nhân đôi dữ liệu.

Lệnh `build_derived_data` dựng hai bảng dẫn xuất từ các bảng thô, cũng chạy lại
an toàn theo cùng cách. Xem mục [Hai tầng bảng](#hai-tầng-bảng) bên dưới.

Kiểm tra: `curl http://localhost:8000/health` trả về
`{"status":"ok","database":"connected"}`. Nếu cơ sở dữ liệu không kết nối được,
endpoint trả mã 503 kèm `{"status":"degraded","database":"disconnected"}`.

## Hai tầng bảng

Tiền tố phân biệt hai tầng: `raw_*` là tầng thô phản chiếu nguyên trạng tệp CSV,
tên trần là tầng dẫn xuất.

| Bảng | Nội dung |
| --- | --- |
| `raw_*` | 9 bảng thô, nguyên trạng, không lọc không biến đổi |
| `orders` | Một dòng mỗi đơn — bốn mốc thời gian, ba khoảng thời gian, cờ trễ, bang khách hàng, điểm đánh giá thấp nhất, trạng thái đơn |
| `order_sellers` | Bảng nối đơn với người bán, dùng khi lọc theo người bán |

`orders` chứa **mọi** đơn kèm cột trạng thái. Việc chỉ lấy đơn đã giao là chuyện
của truy vấn KPI, không phải của bước dựng bảng.

Bốn cột `payment_approval`, `seller_handling`, `carrier_transit` và `is_late` là
cột sinh tự động (`GENERATED ALWAYS AS ... STORED`), không nạp vào được. Riêng
`is_late` là chỗ quan trọng nhất: `Late Order` định nghĩa bằng so sánh ở mức
**ngày lịch**, nên giao đúng ngày cam kết là đúng hạn bất kể mấy giờ. Kiểu `DATE`
của `estimated_delivery_date` một mình không đủ để chặn lỗi — so thẳng dấu thời
gian với nó, Postgres vẫn nâng `DATE` lên nửa đêm và cho ra 7.826 đơn trễ thay vì
6.534. Cột sinh đóng cứng phép so đúng vào lược đồ; truy vấn KPI đọc cờ chứ không
tự tính lại.

Vì cùng lý do đó, **không được thêm `timezone=True`** vào các cột dấu thời gian
trong `app/models/derived.py`: ép kiểu `timestamptz → date` không phải IMMUTABLE,
migration sẽ hỏng.

Lưu ý khi viết truy vấn: `is_late` là `NULL` chứ không phải `false` với đơn chưa
giao, nên cả `WHERE is_late` lẫn `WHERE NOT is_late` đều loại các đơn đó ra. Dùng
`IS TRUE` / `IS NOT TRUE` nếu cần nói rõ ý định.

## Tập đơn biên dùng cho test

`tests/fixtures/edge_case_orders.json` ghim 312 mã đơn chọn có chủ đích, phủ bốn
trường hợp dễ tính sai: giao đúng ngày cam kết, thiếu mốc trung gian, nhiều người
bán, không có đánh giá. Nhóm thiếu mốc trung gian phải chọn có chủ đích vì toàn bộ
dữ liệu chỉ có 15 đơn như vậy trong 99.441 đơn.

Dựng lại tệp này bằng các truy vấn sau — `ORDER BY order_id LIMIT n` cho kết quả
cố định qua mọi lần chạy:

```sql
-- delivered_on_estimated_date
SELECT order_id FROM raw_orders
 WHERE order_status = 'delivered' AND order_delivered_customer_date IS NOT NULL
   AND order_delivered_customer_date::date = order_estimated_delivery_date::date
 ORDER BY order_id LIMIT 100;
-- missing_intermediate_milestone (lấy hết, tổng thể chỉ có 15 đơn)
SELECT order_id FROM raw_orders
 WHERE order_status = 'delivered' AND order_delivered_customer_date IS NOT NULL
   AND (order_approved_at IS NULL OR order_delivered_carrier_date IS NULL)
 ORDER BY order_id;
-- multi_seller
SELECT order_id FROM raw_order_items GROUP BY order_id
 HAVING count(DISTINCT seller_id) > 1 ORDER BY order_id LIMIT 100;
-- no_review
SELECT o.order_id FROM raw_orders o
 WHERE NOT EXISTS (SELECT 1 FROM raw_order_reviews r WHERE r.order_id = o.order_id)
 ORDER BY o.order_id LIMIT 100;
```

## Kiểm thử

```bash
uv run pytest
```

Chạy từ gốc repo, không phải từ `backend/`: cấu hình pytest nằm ở
`pyproject.toml` gốc, đứng ở `backend/` thì pytest lấy nhầm tệp cấu hình và bỏ
qua `asyncio_mode`, làm mọi test bất đồng bộ hỏng.

Test dùng cơ sở dữ liệu riêng tên `shipguard_test`, được tạo tự động ở lần chạy
đầu và không chạm vào cơ sở dữ liệu phát triển. Bộ test tự khẳng định hai URL
khác nhau trước khi chạy migration.

## Cấu hình

Mọi giá trị đọc từ `.env` ở gốc repo — cùng chỗ với `docker-compose.yml`, và cả
hai cùng đọc một tệp. Không có giá trị mặc định trong mã: thiếu biến là hỏng
ngay lúc khởi động kèm thông báo nêu tên biến thiếu.

| Biến | Dùng ở đâu |
| --- | --- |
| `PROJECT_NAME` | Tiêu đề của API |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Docker Compose dựng container |
| `DATABASE_URL` | Ứng dụng và Alembic |
| `TEST_DATABASE_URL` | Chỉ bộ test |

Ghi lược đồ `postgresql://` thuần — mã tự thêm trình điều khiển `+asyncpg`.

## Migration

```bash
uv run alembic -c backend/alembic.ini revision -m "mô tả thay đổi"
uv run alembic -c backend/alembic.ini upgrade head
uv run alembic -c backend/alembic.ini downgrade -1
```
