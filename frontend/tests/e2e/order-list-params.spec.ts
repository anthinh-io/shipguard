import { test, expect } from "@playwright/test";

import {
  DEFAULT_ORDER_LIST_PARAMS,
  EMPTY_ORDER_FILTERS,
  hasActiveFilters,
  parseOrderListParams,
  toOrderListQuery,
  type OrderListParams,
} from "../../app/lib/order-list-params";

// Không mở trình duyệt: đường liên kết gửi cho đồng nghiệp ai cũng sửa tay được, và đây
// là chốt duy nhất biến chuỗi truy vấn tuỳ ý thành tham số hợp lệ trước khi gọi backend.
test("không có tham số nào thì là mặc định: đơn mới đặt nhất, trang 1", () => {
  expect(parseOrderListParams({})).toEqual({
    orderId: "",
    sort: "purchased_at",
    direction: "desc",
    page: 1,
    filters: EMPTY_ORDER_FILTERS,
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
  ).toEqual({
    orderId: "e481f5",
    sort: "order_value",
    direction: "asc",
    page: 1000,
    filters: EMPTY_ORDER_FILTERS,
  });
});

test("giá trị lạ quay về mặc định thay vì để backend trả 422", () => {
  for (const page of ["0", "-3", "abc", "1.5", "", "1e3", "100000000000000000000"]) {
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
  const params: OrderListParams = {
    orderId: "a%_&b",
    sort: "delivered_at",
    direction: "asc",
    page: 12,
    filters: EMPTY_ORDER_FILTERS,
  };

  const query = toOrderListQuery(params);

  expect(parseOrderListParams(Object.fromEntries(new URLSearchParams(query)))).toEqual(
    params,
  );
});

const ALL_FILTERS = {
  order_status: "shipped",
  delivery_outcome: "late",
  purchased_from: "2017-01-01",
  purchased_to: "2018-06-30",
  delivered_from: "2018-01-01",
  delivered_to: "2018-01-31",
  customer_state: "SP",
  seller_id: "6560211a19b47992c3666cc44a7e94c0",
};

test("bộ lọc hợp lệ đi qua nguyên vẹn, tên tham số trùng GET /orders", () => {
  const params = parseOrderListParams(ALL_FILTERS);

  expect(params.filters).toEqual({
    orderStatus: "shipped",
    deliveryOutcome: "late",
    purchased: { from: "2017-01-01", to: "2018-06-30" },
    delivered: { from: "2018-01-01", to: "2018-01-31" },
    customerState: "SP",
    sellerId: "6560211a19b47992c3666cc44a7e94c0",
  });
  expect(Object.fromEntries(new URLSearchParams(toOrderListQuery(params)))).toEqual(
    ALL_FILTERS,
  );
});

test("không có bộ lọc nào thì mọi bộ lọc là null và không ghi gì lên URL", () => {
  expect(parseOrderListParams({}).filters).toEqual(EMPTY_ORDER_FILTERS);
  expect(Object.values(EMPTY_ORDER_FILTERS).every((value) => value === null)).toBe(true);
  expect(toOrderListQuery({ ...DEFAULT_ORDER_LIST_PARAMS, filters: EMPTY_ORDER_FILTERS })).toBe(
    "",
  );
});

test("trạng thái hay kết quả giao lạ thì bỏ qua bộ lọc đó", () => {
  const { filters } = parseOrderListParams({ order_status: "lost", delivery_outcome: "maybe" });

  expect(filters.orderStatus).toBeNull();
  expect(filters.deliveryOutcome).toBeNull();
});

test("khoảng ngày thiếu một đầu, sai ngày hay ngược chiều thì bỏ cả khoảng", () => {
  const halves = [
    { purchased_from: "2018-01-01" },
    { purchased_to: "2018-01-31" },
    { purchased_from: "2018-02-30", purchased_to: "2018-03-31" },
    { purchased_from: "2018-03-31", purchased_to: "2018-03-01" },
  ];
  for (const raw of halves) {
    expect(parseOrderListParams(raw).filters.purchased).toBeNull();
  }
  expect(parseOrderListParams({ delivered_from: "2018-01-01" }).filters.delivered).toBeNull();
  expect(
    toOrderListQuery(parseOrderListParams({ delivered_to: "2018-01-31", page: "2" })),
  ).toBe("page=2");
});

test("bang và người bán rỗng thì không lọc", () => {
  const { filters } = parseOrderListParams({ customer_state: "", seller_id: "" });

  expect(filters.customerState).toBeNull();
  expect(filters.sellerId).toBeNull();
});

test("hasActiveFilters chỉ bật khi có ít nhất một bộ lọc", () => {
  expect(hasActiveFilters(EMPTY_ORDER_FILTERS)).toBe(false);
  expect(hasActiveFilters({ ...EMPTY_ORDER_FILTERS, customerState: "SP" })).toBe(true);
});
