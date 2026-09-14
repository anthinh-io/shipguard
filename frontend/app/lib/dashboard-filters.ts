// Tên tham số trên URL trùng tên tham số của GET /dashboard, nên cùng một chuỗi truy vấn
// dùng được cho cả đường dẫn trang lẫn lời gọi backend — số liệu trên màn hình không thể
// lệch khỏi đường liên kết.
export const COMPARISON_MODES = ["previous", "year_over_year"] as const;

export type ComparisonMode = (typeof COMPARISON_MODES)[number];

export type DashboardFilters = {
  range: { from: string; to: string } | null;
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

type RawSearchParams = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

// Chỉ nhận ngày có thật: ngày sai lọt qua đây làm format.dateTime ném lỗi và sập cả thanh
// bộ lọc. 2018-02-31 đọc ra rồi ghi lại thành 2018-03-03, không khớp chuỗi gốc là bị loại.
function isISODate(value: string | undefined): value is string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return false;
  }
  const date = new Date(value);
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

// Giá trị lạ trên một đường liên kết sửa tay thì bỏ qua như thể không có: người mở link
// vẫn thấy bảng điều khiển, thay vì một thông báo lỗi 422 họ không làm gì được.
export function parseDashboardFilters(raw: RawSearchParams): DashboardFilters {
  const from = first(raw.start_date);
  const to = first(raw.end_date);
  const comparison = first(raw.comparison);

  return {
    // Backend trả 422 nếu chỉ có một đầu, nên thiếu đầu nào là bỏ cả khoảng. Đầu cuối phải
    // sau đầu đầu: lịch không cho chọn khoảng ngược chiều hay chỉ một ngày (xem #9), nên
    // đường liên kết cũng không được dựng ra một bộ lọc mà giao diện không tạo nổi. Chuỗi
    // YYYY-MM-DD so theo thứ tự chữ là đúng thứ tự ngày.
    range: isISODate(from) && isISODate(to) && from < to ? { from, to } : null,
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
