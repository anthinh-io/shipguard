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
    main.py        khởi tạo FastAPI, gắn router, tạo Super Admin lúc khởi động
    core/          cấu hình, kết nối cơ sở dữ liệu, bảo mật
      config.py    đọc .env ở gốc repo
      db.py        engine, session, lớp Base của model
      security.py  băm mật khẩu, ký và xác minh access token
    api/
      deps.py      SessionDep, CurrentUserDep — phụ thuộc dùng chung cho các endpoint
      routes/      mỗi tệp một nhóm endpoint (auth.py: /auth/*, users.py: /me,
                   orders.py: /orders)
    services/      logic nghiệp vụ; route chỉ đọc tham số và gọi vào đây
      auth.py      đăng nhập, cấp và xoay vòng refresh token
      users.py     tạo User, Super Admin, đặt lại và tự đổi mật khẩu
      orders.py    danh sách đơn: tìm tiền tố mã đơn, sắp xếp, phân trang
      queries.py   mảnh truy vấn dùng chung: vị ngữ DELIVERED, like_prefix
    scripts/       lệnh chạy tay: nạp dữ liệu, đặt lại mật khẩu Super Admin
    alembic/       migration
  tests/
  alembic.ini
  pyproject.toml   phụ thuộc riêng của backend
```

Bố cục theo `fastapi/full-stack-fastapi-template`.

## Khởi động

Chép tệp môi trường rồi điền `POSTGRES_USER`, `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`
và ba biến `SUPER_ADMIN_*` của bạn:

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

Kiểm tra tiếp: `curl http://localhost:8000/dashboard -H 'Authorization: Bearer
<access_token>'` (lấy token ở mục [Đăng nhập](#đăng-nhập)) trả về kỳ báo cáo mặc
định kèm khối KPI; thiếu token thì 401. Truyền `?start_date=...&end_date=...` để chọn kỳ khác — hai tham
số phải đi cùng nhau, thiếu một bên thì endpoint trả mã 422.

`GET /orders` (cũng đòi token) trả một trang 50 đơn: `{"items", "total", "page",
"page_size"}`. Tham số, đều không bắt buộc:

| Tham số | Giá trị | Mặc định |
| --- | --- | --- |
| `order_id` | Tiền tố mã đơn, không phân biệt hoa thường; `%` và `_` là ký tự thường | không lọc |
| `sort` | `purchased_at`, `estimated_delivery_date`, `delivered_at`, `order_value` | `purchased_at` |
| `direction` | `asc`, `desc` | `desc` |
| `page` | Số nguyên từ 1; vượt quá trang cuối thì `items` rỗng, `total` giữ nguyên | `1` |

Giá trị ngoài danh sách nhận 422. Ô trống (`delivered_at` của đơn chưa giao,
`order_value` của đơn không có sản phẩm) luôn nằm cuối, cả khi sắp tăng lẫn giảm.
Đơn trùng giá trị sắp xếp được xếp tiếp theo `order_id`, nên lật trang không trả
trùng hay bỏ sót đơn. Mỗi dòng mang `delivery_outcome`: `on_time` / `late` chỉ với
`Delivered Order`, mọi đơn khác là `no_outcome` — kể cả đơn đã hủy lỡ có ngày giao.
`order_value` là số thực, không phải chuỗi thập phân.

## Đăng nhập

Cơ chế token theo `docs/adr/0006-goi-thang-backend-kem-xac-thuc-jwt.md`: access
token JWT sống 15 phút gửi qua header `Authorization: Bearer`, refresh token sống
7 ngày trong cookie `httpOnly` chỉ đi kèm `/auth/*`.

Lần khởi động đầu tiên tạo `Super Admin` từ `SUPER_ADMIN_EMAIL`,
`SUPER_ADMIN_PASSWORD`, `SUPER_ADMIN_NAME`. Từ đó các biến này bị bỏ qua — đổi
chúng rồi khởi động lại không tạo thêm hay sửa tài khoản nào. Backend **không
khởi động** nếu chưa chạy migration, hoặc nếu `SUPER_ADMIN_EMAIL` trùng một
`User` thường đã có; thông báo lỗi nêu rõ lý do.

```bash
curl -i -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"..."}'
curl http://localhost:8000/me -H 'Authorization: Bearer <access_token>'
```

| Endpoint | Việc |
| --- | --- |
| `POST /auth/login` | Trả access token, đặt cookie refresh token. Sai mật khẩu, email không tồn tại và tài khoản bị khóa đều nhận cùng một 401 |
| `POST /auth/refresh` | Đổi cookie hiện có lấy access token và cookie mới; cookie cũ bị thu hồi, dùng lại nhận 401 |
| `POST /auth/logout` | Thu hồi cookie hiện có và xóa nó khỏi trình duyệt |
| `POST /auth/password` | Tự đổi mật khẩu, cần access token; body `{"current_password", "new_password"}`. Thu hồi mọi refresh token của người đó rồi trả access token và cookie mới cho phiên đang dùng — mọi phiên khác bị đăng xuất. Sai mật khẩu cũ nhận 400, mật khẩu mới dưới 8 ký tự nhận 422 (không phải 401: frontend hiểu 401 là phiên hết hạn) |
| `GET /me` | Người đang đăng nhập: email, tên, vai trò, claim. Thiếu token hợp lệ thì 401 |

Mọi route khác đều đòi access token hợp lệ, thiếu thì 401 — trừ `/health` và
`/auth/*` (`/auth/logout` chỉ cần cookie; `/auth/password` là ngoại lệ, vẫn đòi
access token).

Cookie refresh token chưa đặt cờ `Secure` vì môi trường phát triển chạy http.
Triển khai qua HTTPS thì phải bật lại.

### Đặt lại mật khẩu Super Admin

Không có luồng quên mật khẩu qua email. Người có quyền vào máy chủ chạy:

```bash
uv run python -m app.scripts.reset_super_admin_password
```

Lệnh hỏi mật khẩu mới hai lần (tối thiểu 8 ký tự, không hiện khi gõ). Đặt lại
xong, mọi phiên cũ của Super Admin bị đăng xuất.

## Hai tầng bảng

Tiền tố phân biệt hai tầng: `raw_*` là tầng thô phản chiếu nguyên trạng tệp CSV,
tên trần là tầng dẫn xuất.

| Bảng | Nội dung |
| --- | --- |
| `raw_*` | 9 bảng thô, nguyên trạng, không lọc không biến đổi |
| `orders` | Một dòng mỗi đơn — bốn mốc thời gian, ba khoảng thời gian, cờ trễ, bang khách hàng, điểm đánh giá thấp nhất, trạng thái đơn, giá trị đơn |
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

`order_value` là tổng `price + freight_value` của các dòng sản phẩm, tính sẵn lúc
dựng bảng; 775 đơn không có sản phẩm nào để `NULL`. Đây không phải số tiền khách
thanh toán: 303 đơn lệch tổng thanh toán hơn 1 xu, và như vậy là đúng (so bằng
tuyệt đối ra 576, vì trả góp làm tròn từng kỳ). Bộ số vàng tính thẳng từ CSV nằm
ở `tests/test_order_value_golden.py`.

Tìm mã đơn dùng chỉ mục biểu thức `lower(order_id) text_pattern_ops`. Cơ sở dữ
liệu chạy collation `en_US.utf8`, mà btree thường theo collation đó — kể cả khoá
chính — không phục vụ được `LIKE 'abc%'`; `ILIKE` thì không đi qua chỉ mục kiểu
này. Truy vấn tiền tố mã đơn vì thế phải viết đúng dạng
`lower(order_id) LIKE '...%'`.

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

`tests/fixtures/edge_case_filters.json` là tệp anh em, ghim những thứ *không phải* mã
đơn: người bán dưới ngưỡng mẫu nhỏ, người bán nhiều đơn nhất, và một kỳ báo cáo mà cả
hai kỳ đối chiếu đều rỗng. Để riêng vì `edge_case_orders.json` được đọc theo kiểu
"mọi nhóm đều là danh sách mã đơn", trộn vào sẽ làm hỏng cách đọc đó.

```sql
-- small_sample_sellers (2.343 người bán như vậy; lấy 20 mã đầu cho cố định)
SELECT os.seller_id FROM order_sellers os
  JOIN orders o ON o.order_id = os.order_id
 WHERE o.order_status = 'delivered' AND o.delivered_to_customer_at IS NOT NULL
 GROUP BY os.seller_id HAVING count(*) < 30
 ORDER BY os.seller_id LIMIT 20;
-- busiest_seller
SELECT os.seller_id FROM order_sellers os
  JOIN orders o ON o.order_id = os.order_id
 WHERE o.order_status = 'delivered' AND o.delivered_to_customer_at IS NOT NULL
 GROUP BY os.seller_id ORDER BY count(*) DESC LIMIT 1;
-- empty_comparison_period: 10/2016 là tháng đầu tiên có đơn giao (205 đơn), nên kỳ
-- liền trước (9/2016) và cùng kỳ năm trước (10/2015) đều không có đơn nào.
SELECT date_trunc('month', delivered_to_customer_at) AS month, count(*)
  FROM orders WHERE order_status = 'delivered'
   AND delivered_to_customer_at IS NOT NULL
 GROUP BY 1 ORDER BY 1 LIMIT 3;
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
| `CORS_ALLOWED_ORIGINS` | Origin của frontend, phân tách bằng dấu phẩy. Trình duyệt gọi thẳng backend nên thiếu origin đúng là màn hình trắng mà phía máy chủ không báo lỗi gì — xem `docs/adr/0006-goi-thang-backend-kem-xac-thuc-jwt.md` |
| `JWT_SECRET_KEY` | Khóa ký access token. Đổi khóa thì mọi access token đang có hết hiệu lực ngay |
| `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD`, `SUPER_ADMIN_NAME` | Chỉ đọc ở lần khởi động đầu, khi chưa có Super Admin — xem [Đăng nhập](#đăng-nhập) |

Ghi lược đồ `postgresql://` thuần — mã tự thêm trình điều khiển `+asyncpg`.

## Migration

```bash
uv run alembic -c backend/alembic.ini revision -m "mô tả thay đổi"
uv run alembic -c backend/alembic.ini upgrade head
uv run alembic -c backend/alembic.ini downgrade -1
```
