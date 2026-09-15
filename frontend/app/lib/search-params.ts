// Đọc chuỗi truy vấn dùng chung cho mọi trang giữ trạng thái trên URL.

export type RawSearchParams = Record<string, string | string[] | undefined>;

// Khoảng ngày dạng "YYYY-MM-DD", tính cả hai đầu.
export type DayRange = { from: string; to: string };

export function first(value: string | string[] | undefined): string | undefined {
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

// Backend trả 422 nếu chỉ có một đầu, nên thiếu đầu nào là bỏ cả khoảng. Đầu cuối phải
// sau đầu đầu: lịch không cho chọn khoảng ngược chiều hay chỉ một ngày (xem #9), nên
// đường liên kết cũng không được dựng ra một bộ lọc mà giao diện không tạo nổi. Chuỗi
// YYYY-MM-DD so theo thứ tự chữ là đúng thứ tự ngày.
//
// allowSingleDay chỉ /orders bật: drill-down từ biểu đồ (#25) dựng được khoảng một ngày
// dù lịch không tạo được — nhóm theo ngày, hay nhóm tuần bị kẹp vào kỳ chỉ còn một ngày.
// Bảng điều khiển giữ luật cũ vì không có đường nào dẫn tới kỳ một ngày ở đó.
export function parseDayRange(
  from: string | string[] | undefined,
  to: string | string[] | undefined,
  { allowSingleDay = false }: { allowSingleDay?: boolean } = {},
): DayRange | null {
  const start = first(from);
  const end = first(to);
  if (!isISODate(start) || !isISODate(end)) {
    return null;
  }
  return start < end || (allowSingleDay && start === end) ? { from: start, to: end } : null;
}
