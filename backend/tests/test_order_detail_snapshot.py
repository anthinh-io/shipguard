import json
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token

# Ảnh chụp phản hồi của 312 đơn biên, lấy lúc trang chi tiết còn đọc bảng thô. Bài này là
# cổng chặn của việc chuyển đường đọc sang lớp dẫn xuất: sai lệch âm thầm ở vài trường của
# vài đơn không làm trang hỏng, nên không có cách nào khác để bắt.
#
# KHÔNG chụp lại tệp này để làm một bài test đỏ thành xanh. Đỏ nghĩa là phản hồi đã đổi.
# Công thức dựng lại nằm trong backend/README.md.
SNAPSHOT: dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures" / "order_detail_snapshot.json").read_text("utf-8")
)

pytestmark = pytest.mark.usefixtures("derived_data")


@pytest.fixture(autouse=True)
def signed_in(client: AsyncClient) -> None:
    token = create_access_token(1, "operations_staff", [])
    client.headers["Authorization"] = f"Bearer {token}"


async def test_order_detail_matches_the_snapshot_taken_before_the_move(
    client: AsyncClient,
) -> None:
    assert len(SNAPSHOT) == 312

    # Gom mọi mã đơn lệch rồi mới khẳng định: dừng ở đơn đầu tiên thì không biết một trường
    # hỏng ở một đơn hay cả một khối hỏng ở mọi đơn.
    differing = []
    for order_id, expected in SNAPSHOT.items():
        response = await client.get(f"/orders/{order_id}")
        assert response.status_code == 200, response.text
        if response.json() != expected:
            differing.append(order_id)

    assert differing == []
