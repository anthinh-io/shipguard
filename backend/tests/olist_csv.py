"""Đọc thẳng tệp CSV Olist làm nguồn đối chiếu độc lập cho test (ADR-0010).

Lớp dẫn xuất là thứ đang được kiểm, nên con số kỳ vọng không được lấy từ chính cơ sở dữ
liệu ấy: cùng một lỗi nằm ở cả hai vế thì phép so vẫn xanh. Tệp CSV trên đĩa là nguồn
duy nhất nằm ngoài, và từ khi bảng thô bị xoá thì nó cũng là nguồn duy nhất còn lại.

utf-8-sig chứ không phải utf-8: product_category_name_translation.csv có BOM, đọc bằng
utf-8 làm tên cột đầu tiên dính một ký tự vô hình ở đầu.
"""

import csv
from functools import cache

# Dùng chung hằng với bước dựng chứ không khai lại đường dẫn: test phải đọc đúng thư mục
# bước dựng đọc, nếu không hai bên so nhau trên hai bộ tệp khác nhau mà không ai biết.
# Tính độc lập nằm ở chỗ đây là tệp CSV chứ không phải bảng trong cơ sở dữ liệu, không
# nằm ở chỗ khai lại đường dẫn lần thứ hai.
from app.scripts.build_derived_data import CSV_DIR


# Nhớ đệm vì một tệp được nhiều bài test trong cùng phiên đọc lại, và tệp dòng hàng có
# 112.650 dòng. Trả về tuple chứ không phải list vì mọi bài gọi dùng chung một giá trị:
# tuple chặn được việc thêm bớt dòng, dù các dict bên trong thì vẫn sửa được.
@cache
def read_rows(filename: str) -> tuple[dict[str, str], ...]:
    with open(CSV_DIR / filename, encoding="utf-8-sig", newline="") as f:
        return tuple(csv.DictReader(f))


def row_count(filename: str) -> int:
    return len(read_rows(filename))
