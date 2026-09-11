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
uv run fastapi dev backend/app/main.py
```

`--wait` chặn cho tới khi Postgres nhận kết nối. Thiếu nó thì lệnh migration
ngay sau đó có thể chạy trong lúc cơ sở dữ liệu còn đang khởi tạo và bị từ chối.

Lệnh `load_raw_data` nạp 9 tệp CSV Olist trong `datasets/raw/` vào các bảng
`raw_*`, nguyên trạng không lọc hay biến đổi. Chạy lại an toàn: mỗi bảng được
xoá sạch (`TRUNCATE`) rồi nạp lại trong cùng một transaction trước khi nạp,
nên không bao giờ bị nhân đôi dữ liệu.

Kiểm tra: `curl http://localhost:8000/health` trả về
`{"status":"ok","database":"connected"}`. Nếu cơ sở dữ liệu không kết nối được,
endpoint trả mã 503 kèm `{"status":"degraded","database":"disconnected"}`.

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
