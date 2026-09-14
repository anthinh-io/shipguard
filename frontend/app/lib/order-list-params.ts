// Tên tham số trên URL trùng tên tham số của GET /orders, nên cùng một chuỗi truy vấn
// dùng được cho cả đường dẫn trang lẫn lời gọi backend.
export const ORDER_SORTS = [
  "purchased_at",
  "estimated_delivery_date",
  "delivered_at",
  "order_value",
] as const;

export type OrderSort = (typeof ORDER_SORTS)[number];
export type SortDirection = "asc" | "desc";

export type OrderListParams = {
  orderId: string;
  sort: OrderSort;
  direction: SortDirection;
  page: number;
};

export const DEFAULT_ORDER_LIST_PARAMS: OrderListParams = {
  orderId: "",
  sort: "purchased_at",
  direction: "desc",
  page: 1,
};

type RawSearchParams = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

// Giá trị lạ trên một đường liên kết sửa tay quay về mặc định: người mở link vẫn thấy một
// danh sách, thay vì một thông báo lỗi 422 họ không làm gì được.
export function parseOrderListParams(raw: RawSearchParams): OrderListParams {
  const sort = first(raw.sort);
  const direction = first(raw.direction);
  const page = first(raw.page);

  return {
    orderId: first(raw.order_id)?.trim() ?? "",
    sort: ORDER_SORTS.find((value) => value === sort) ?? DEFAULT_ORDER_LIST_PARAMS.sort,
    direction:
      direction === "asc" || direction === "desc"
        ? direction
        : DEFAULT_ORDER_LIST_PARAMS.direction,
    // Chỉ nhận chuỗi toàn chữ số: Number() còn nhận "1e3" và "1.5".
    page: page && /^[1-9]\d*$/.test(page) ? Number(page) : DEFAULT_ORDER_LIST_PARAMS.page,
  };
}

export function toOrderListQuery(params: OrderListParams): string {
  const query = new URLSearchParams();
  const orderId = params.orderId.trim();
  if (orderId) {
    query.set("order_id", orderId);
  }
  if (params.sort !== DEFAULT_ORDER_LIST_PARAMS.sort) {
    query.set("sort", params.sort);
  }
  if (params.direction !== DEFAULT_ORDER_LIST_PARAMS.direction) {
    query.set("direction", params.direction);
  }
  if (params.page !== DEFAULT_ORDER_LIST_PARAMS.page) {
    query.set("page", String(params.page));
  }
  return query.toString();
}
