import { test, expect } from "@playwright/test";

import {
  DEFAULT_ORDER_LIST_PARAMS,
  parseOrderListParams,
  toOrderListQuery,
} from "../../app/lib/order-list-params";

// Không mở trình duyệt: đường liên kết gửi cho đồng nghiệp ai cũng sửa tay được, và đây
// là chốt duy nhất biến chuỗi truy vấn tuỳ ý thành tham số hợp lệ trước khi gọi backend.
test("không có tham số nào thì là mặc định: đơn mới đặt nhất, trang 1", () => {
  expect(parseOrderListParams({})).toEqual({
    orderId: "",
    sort: "purchased_at",
    direction: "desc",
    page: 1,
  });
  expect(DEFAULT_ORDER_LIST_PARAMS).toEqual(parseOrderListParams({}));
});

test("tham số hợp lệ đi qua nguyên vẹn, mã đơn được cắt khoảng trắng", () => {
  expect(
    parseOrderListParams({
      order_id: "  e481f5 ",
      sort: "order_value",
      direction: "asc",
      page: "1000",
    }),
  ).toEqual({ orderId: "e481f5", sort: "order_value", direction: "asc", page: 1000 });
});

test("giá trị lạ quay về mặc định thay vì để backend trả 422", () => {
  for (const page of ["0", "-3", "abc", "1.5", "", "1e3"]) {
    expect(parseOrderListParams({ page }).page).toBe(1);
  }
  expect(parseOrderListParams({ sort: "customer_state" }).sort).toBe("purchased_at");
  expect(parseOrderListParams({ direction: "up" }).direction).toBe("desc");
});

test("tham số lặp lại thì lấy giá trị đầu", () => {
  expect(parseOrderListParams({ page: ["3", "7"], order_id: ["ab", "cd"] })).toMatchObject({
    page: 3,
    orderId: "ab",
  });
});

test("mặc định không ghi lên URL, để đường liên kết gọn", () => {
  expect(toOrderListQuery(DEFAULT_ORDER_LIST_PARAMS)).toBe("");
  expect(toOrderListQuery({ ...DEFAULT_ORDER_LIST_PARAMS, orderId: "   " })).toBe("");
  expect(toOrderListQuery({ ...DEFAULT_ORDER_LIST_PARAMS, page: 3 })).toBe("page=3");
});

test("ghi ra rồi đọc lại thì được đúng tập tham số, kể cả ký tự đặc biệt", () => {
  const params = {
    orderId: "a%_&b",
    sort: "delivered_at",
    direction: "asc",
    page: 12,
  } as const;

  const query = toOrderListQuery(params);

  expect(parseOrderListParams(Object.fromEntries(new URLSearchParams(query)))).toEqual(
    params,
  );
});
