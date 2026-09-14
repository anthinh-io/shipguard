import sqlalchemy as sa

from app.models.derived import orders

# Delivered Order theo CONTEXT.md: đơn đã tới tay khách và có ngày giao thực tế. Đây là
# tập đơn duy nhất được tính vào KPI — bảng dẫn xuất cố ý giữ mọi đơn kèm cột trạng
# thái, việc lọc thuộc về truy vấn KPI. Dựng bằng Core chứ không phải chuỗi SQL để các
# truy vấn sau còn ghép thêm điều kiện lọc và mệnh đề gom nhóm lên trên.
DELIVERED = sa.and_(
    orders.c.order_status == "delivered",
    orders.c.delivered_to_customer_at.is_not(None),
)


def like_prefix(query: str) -> str:
    # seller_city nhận chuỗi tự do người dùng gõ vào, nên "%" và "_" phải thành ký tự
    # thường. Không thoát thì gõ đúng một dấu "%" sẽ khớp toàn bộ 3.095 người bán.
    # Dấu chéo ngược phải thoát trước, nếu không nó sẽ thoát nhầm hai lần sau đó.
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"{escaped}%"
