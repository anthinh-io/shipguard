// Tên tham số trên URL trùng tên tham số của GET /dashboard, nên cùng một chuỗi truy vấn
// dùng được cho cả đường dẫn trang lẫn lời gọi backend — số liệu trên màn hình không thể
// lệch khỏi đường liên kết.
import {
  first,
  parseDayRange,
  type DayRange,
  type RawSearchParams,
} from "./search-params";

export const COMPARISON_MODES = ["previous", "year_over_year"] as const;

export type ComparisonMode = (typeof COMPARISON_MODES)[number];

export type DashboardFilters = {
  range: DayRange | null;
  customerState: string | null;
  // Chỉ mã, vì URL chỉ mang mã. Nhãn trên nút tự tra bang của người bán — xem
  // seller-combobox.tsx.
  sellerId: string | null;
  comparison: ComparisonMode | null;
};

// null ở mỗi trường nghĩa là không gắn tham số đó vào chuỗi truy vấn, chứ không phải
// "gắn giá trị mặc định" — backend tự giải kỳ mặc định hoặc không lọc.
export const EMPTY_FILTERS: DashboardFilters = {
  range: null,
  customerState: null,
  sellerId: null,
  comparison: null,
};

// Giá trị lạ trên một đường liên kết sửa tay thì bỏ qua như thể không có: người mở link
// vẫn thấy bảng điều khiển, thay vì một thông báo lỗi 422 họ không làm gì được.
export function parseDashboardFilters(raw: RawSearchParams): DashboardFilters {
  const comparison = first(raw.comparison);

  return {
    range: parseDayRange(raw.start_date, raw.end_date),
    customerState: first(raw.customer_state) || null,
    sellerId: first(raw.seller_id) || null,
    comparison: COMPARISON_MODES.find((mode) => mode === comparison) ?? null,
  };
}

export function toDashboardQuery(filters: DashboardFilters): string {
  const query = new URLSearchParams();
  if (filters.range) {
    query.set("start_date", filters.range.from);
    query.set("end_date", filters.range.to);
  }
  if (filters.customerState) {
    query.set("customer_state", filters.customerState);
  }
  if (filters.sellerId) {
    query.set("seller_id", filters.sellerId);
  }
  if (filters.comparison) {
    query.set("comparison", filters.comparison);
  }
  return query.toString();
}
