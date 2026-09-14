// Cách hiện dữ liệu Olist dùng chung cho danh sách đơn và trang chi tiết đơn.

export type DeliveryOutcome = "on_time" | "late" | "no_outcome";

// Ngoại lệ có chủ ý với quy tắc "đừng dựng Intl tại chỗ" của README: Order Value là tiền
// Brazil và luôn hiện theo kiểu Brazil "R$ 13.664,08", ở cả hai ngôn ngữ giao diện. Bộ
// định dạng này cố ý không đổi theo nút chuyển ngữ, nên đóng cứng ở phạm vi module là
// đúng — useFormatter luôn dùng ngôn ngữ giao diện và không cho đổi riêng từng lần gọi.
export const BRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

// Backend trả dấu thời gian không kèm múi giờ ("2018-10-17T02:30:18"). new Date() đọc
// chuỗi đó theo giờ máy, rồi fullDate hiện theo UTC — máy ở phía đông UTC lùi mất một
// ngày. Cắt lấy phần ngày thì new Date() đọc thành nửa đêm UTC, khớp quy ước ADR-0005.
export function utcDay(value: string): Date {
  return new Date(value.slice(0, 10));
}

// Cùng lý do, cho chỗ cần cả giờ: gắn "Z" để đọc dấu thời gian như UTC, rồi hiện bằng
// format fullDateTime vốn cũng khai timeZone UTC — giờ trên màn hình đúng giờ trong dữ liệu.
export function utcTimestamp(value: string): Date {
  return new Date(`${value}Z`);
}

export const OUTCOME_CLASS: Record<DeliveryOutcome, string> = {
  on_time:
    "border-emerald-600/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  late: "border-red-600/30 bg-red-500/10 text-red-700 dark:text-red-400",
  no_outcome: "text-muted-foreground",
};
