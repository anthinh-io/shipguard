import {
  first,
  parseDayRange,
  type DayRange,
  type RawSearchParams,
} from "./search-params";

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

// Order Status theo CONTEXT.md, theo thứ tự vòng đời để ô chọn đọc xuôi.
export const ORDER_STATUSES = [
  "created",
  "approved",
  "invoiced",
  "processing",
  "shipped",
  "delivered",
  "canceled",
  "unavailable",
] as const;

export type OrderStatus = (typeof ORDER_STATUSES)[number];

export const DELIVERY_OUTCOMES = ["on_time", "late", "no_outcome"] as const;

export type DeliveryOutcome = (typeof DELIVERY_OUTCOMES)[number];

// Risk Level và Handling Status theo CONTEXT.md (#36): cả hai tính trên lần đánh giá mới
// nhất của đơn, backend trả nguyên chuỗi này qua GET /orders — tên khớp field của
// OrderListItem, cùng lý do với các enum khác trong file này.
export const RISK_LEVELS = ["high", "low", "not_assessed"] as const;

export type RiskLevel = (typeof RISK_LEVELS)[number];

export const HANDLING_STATUSES = ["unhandled", "handled"] as const;

export type HandlingStatus = (typeof HANDLING_STATUSES)[number];

export type OrderFilters = {
  orderStatus: OrderStatus | null;
  deliveryOutcome: DeliveryOutcome | null;
  purchased: DayRange | null;
  delivered: DayRange | null;
  customerState: string | null;
  // Chỉ mã, vì URL chỉ mang mã. Nhãn trên nút tự tra bang của người bán — xem
  // seller-combobox.tsx.
  sellerId: string | null;
  riskLevel: RiskLevel | null;
  handlingStatus: HandlingStatus | null;
};

export type OrderListParams = {
  orderId: string;
  sort: OrderSort;
  direction: SortDirection;
  page: number;
  filters: OrderFilters;
};

// null ở mỗi trường nghĩa là không gắn tham số đó vào chuỗi truy vấn.
export const EMPTY_ORDER_FILTERS: OrderFilters = {
  orderStatus: null,
  deliveryOutcome: null,
  purchased: null,
  delivered: null,
  customerState: null,
  sellerId: null,
  riskLevel: null,
  handlingStatus: null,
};

export const DEFAULT_ORDER_LIST_PARAMS: OrderListParams = {
  orderId: "",
  sort: "purchased_at",
  direction: "desc",
  page: 1,
  filters: EMPTY_ORDER_FILTERS,
};

export function hasActiveFilters(filters: OrderFilters): boolean {
  return Object.values(filters).some((value) => value !== null);
}

// Giá trị lạ trên một đường liên kết sửa tay quay về mặc định: người mở link vẫn thấy một
// danh sách, thay vì một thông báo lỗi 422 họ không làm gì được.
export function parseOrderListParams(raw: RawSearchParams): OrderListParams {
  const sort = first(raw.sort);
  const direction = first(raw.direction);
  const page = first(raw.page);
  const orderStatus = first(raw.order_status);
  const deliveryOutcome = first(raw.delivery_outcome);
  const riskLevel = first(raw.risk_level);
  const handlingStatus = first(raw.handling_status);

  return {
    orderId: first(raw.order_id)?.trim() ?? "",
    sort: ORDER_SORTS.find((value) => value === sort) ?? DEFAULT_ORDER_LIST_PARAMS.sort,
    direction:
      direction === "asc" || direction === "desc"
        ? direction
        : DEFAULT_ORDER_LIST_PARAMS.direction,
    // Chỉ nhận chuỗi toàn chữ số: Number() còn nhận "1e3" và "1.5". Số quá lớn thì làm
    // tròn mất chữ số, và backend từ chối trang vượt giới hạn OFFSET của Postgres.
    page:
      page && /^[1-9]\d*$/.test(page) && Number.isSafeInteger(Number(page))
        ? Number(page)
        : DEFAULT_ORDER_LIST_PARAMS.page,
    filters: {
      orderStatus: ORDER_STATUSES.find((value) => value === orderStatus) ?? null,
      deliveryOutcome: DELIVERY_OUTCOMES.find((value) => value === deliveryOutcome) ?? null,
      // Một đầu thì bỏ cả khoảng: người mở link thấy danh sách chưa lọc theo khoảng đó,
      // giống lúc mới chọn ngày đầu trên lịch. Một ngày thì giữ — xem parseDayRange.
      purchased: parseDayRange(raw.purchased_from, raw.purchased_to, { allowSingleDay: true }),
      delivered: parseDayRange(raw.delivered_from, raw.delivered_to, { allowSingleDay: true }),
      customerState: first(raw.customer_state) || null,
      sellerId: first(raw.seller_id) || null,
      riskLevel: RISK_LEVELS.find((value) => value === riskLevel) ?? null,
      handlingStatus: HANDLING_STATUSES.find((value) => value === handlingStatus) ?? null,
    },
  };
}

export function toOrderListQuery(params: OrderListParams): string {
  const query = new URLSearchParams();
  const orderId = params.orderId.trim();
  if (orderId) {
    query.set("order_id", orderId);
  }
  const { filters } = params;
  if (filters.orderStatus) {
    query.set("order_status", filters.orderStatus);
  }
  if (filters.deliveryOutcome) {
    query.set("delivery_outcome", filters.deliveryOutcome);
  }
  if (filters.purchased) {
    query.set("purchased_from", filters.purchased.from);
    query.set("purchased_to", filters.purchased.to);
  }
  if (filters.delivered) {
    query.set("delivered_from", filters.delivered.from);
    query.set("delivered_to", filters.delivered.to);
  }
  if (filters.customerState) {
    query.set("customer_state", filters.customerState);
  }
  if (filters.sellerId) {
    query.set("seller_id", filters.sellerId);
  }
  if (filters.riskLevel) {
    query.set("risk_level", filters.riskLevel);
  }
  if (filters.handlingStatus) {
    query.set("handling_status", filters.handlingStatus);
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

// Đường liên kết drill-down từ bảng điều khiển (#25): đơn trễ đã giao trong `delivered`,
// cùng bang và người bán đang lọc. Chỉ bộ lọc, không sắp xếp hay trang, và không có kỳ so
// sánh — danh sách đơn không có khái niệm đó.
export function lateOrdersQuery(
  delivered: DayRange,
  customerState: string | null,
  sellerId: string | null,
): string {
  return toOrderListQuery({
    ...DEFAULT_ORDER_LIST_PARAMS,
    filters: {
      ...EMPTY_ORDER_FILTERS,
      deliveryOutcome: "late",
      delivered,
      customerState,
      sellerId,
    },
  });
}
