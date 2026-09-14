from datetime import date, datetime, time, timedelta

import sqlalchemy as sa

from app.models.derived import order_sellers, orders

# Delivered Order theo CONTEXT.md: đơn đã tới tay khách và có ngày giao thực tế. Đây là
# tập đơn duy nhất được tính vào KPI — bảng dẫn xuất cố ý giữ mọi đơn kèm cột trạng
# thái, việc lọc thuộc về truy vấn KPI. Dựng bằng Core chứ không phải chuỗi SQL để các
# truy vấn sau còn ghép thêm điều kiện lọc và mệnh đề gom nhóm lên trên.
DELIVERED = sa.and_(
    orders.c.order_status == "delivered",
    orders.c.delivered_to_customer_at.is_not(None),
)


def like_prefix(query: str) -> str:
    # Ô gợi ý người bán và ô tìm mã đơn đều nhận chuỗi tự do người dùng gõ vào, nên "%"
    # và "_" phải thành ký tự thường. Không thoát thì gõ đúng một dấu "%" sẽ khớp toàn
    # bộ 3.095 người bán, hay cả 99.441 đơn. Người gọi phải truyền escape="\\" cho LIKE.
    # Dấu chéo ngược phải thoát trước, nếu không nó sẽ thoát nhầm hai lần sau đó.
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"{escaped}%"


def within_days(
    column: sa.ColumnElement, start_date: date, end_date: date
) -> sa.ColumnElement[bool]:
    # Chặn bằng dấu thời gian thay vì ép column::date, để chỉ mục trên cột còn dùng được.
    # Cận trên là nửa đêm đầu ngày kế tiếp, nên kết quả trùng khít với phép so ở mức ngày
    # lịch, tính cả ngày đầu lẫn ngày cuối.
    return sa.and_(
        column >= datetime.combine(start_date, time.min),
        column < datetime.combine(end_date + timedelta(days=1), time.min),
    )


def sold_by(seller_id: str) -> sa.ColumnElement[bool]:
    # EXISTS chứ không JOIN nên vẫn đúng một dòng mỗi đơn. Đơn ghép nhiều người bán vì vậy
    # thuộc về MỌI người bán tham gia — đúng CONTEXT.md mục Multi-Seller Order. Đừng khử.
    return sa.exists().where(
        sa.and_(
            order_sellers.c.order_id == orders.c.order_id,
            order_sellers.c.seller_id == seller_id,
        )
    )
