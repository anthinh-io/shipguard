import { cookies } from "next/headers";
import { getRequestConfig } from "next-intl/server";

import { LOCALE_COOKIE, defaultLocale, isLocale } from "./config";

export default getRequestConfig(async () => {
  const cookie = (await cookies()).get(LOCALE_COOKIE)?.value;
  const locale = isLocale(cookie) ? cookie : defaultLocale;

  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
    formats: {
      dateTime: {
        // dateStyle "short" cho năm hai chữ số ("1/9/17"), mơ hồ với một kỳ báo cáo
        // trải nhiều năm; nêu rõ từng thành phần để ra 01/09/2017.
        //
        // timeZone UTC là bắt buộc, không phải tuỳ chọn: new Date("2017-09-01") đọc
        // chuỗi chỉ có ngày thành nửa đêm UTC, nên máy đặt ở múi giờ phía tây UTC sẽ
        // hiện 31/08/2017 — lệch đúng một ngày ở chính cái ranh giới mà cả tính năng
        // này xoay quanh. Đặt trong format có tên chứ không đặt toàn cục, để ticket sau
        // hiện mốc thời gian thật không thừa hưởng nhầm.
        fullDate: {
          day: "2-digit",
          month: "2-digit",
          year: "numeric",
          timeZone: "UTC",
        },
        // Mốc thời gian trên trang chi tiết đơn (#21), nơi giờ có ý nghĩa: duyệt thanh
        // toán sau vài phút hay sau một ngày là hai chuyện khác nhau. Dữ liệu Olist theo
        // quy ước UTC của ADR-0005 — đi cùng utcTimestamp trong app/lib/order-format.ts.
        fullDateTime: {
          day: "2-digit",
          month: "2-digit",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit",
          hourCycle: "h23",
          timeZone: "UTC",
        },
        // Mốc thời gian thật, như thời điểm viết ghi chú nội bộ (#22): hiện theo múi giờ
        // trình duyệt người xem, khác dữ liệu Olist theo quy ước UTC của ADR-0005. Cố ý
        // không khai timeZone, và chỗ gọi phải tự truyền timeZone của trình duyệt: không
        // truyền thì next-intl dùng múi giờ mà NextIntlClientProvider nhận từ máy chủ,
        // không phải của trình duyệt.
        localDateTime: {
          day: "2-digit",
          month: "2-digit",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit",
          hourCycle: "h23",
        },
        // Nhãn trục hoành của biểu đồ xu hướng (#9). Cùng lý do timeZone UTC với
        // fullDate — nếu không, máy ở múi giờ phía tây UTC lệch mất một ngày.
        axisDate: { day: "2-digit", month: "2-digit", timeZone: "UTC" },
        axisMonth: { month: "short", year: "numeric", timeZone: "UTC" },
      },
      number: {
        percent: {
          style: "percent",
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        },
        // Số ngày của ba chặng thời gian (#8) — trung vị và phân vị 90 là số thực,
        // không phải số nguyên, nên cần một format riêng thay vì format() mặc định.
        days: {
          maximumFractionDigits: 2,
        },
        // percent đang cố định 2 chữ số thập phân — hợp với ô KPI, quá dài cho vạch
        // trục của biểu đồ xu hướng (#9).
        percentAxis: {
          style: "percent",
          maximumFractionDigits: 0,
        },
        // Ba định dạng mức chênh giữa hai kỳ (#13). signDisplay "exceptZero" để dấu +
        // hiện ra với mức tăng — không có nó thì chỉ mức giảm mới mang dấu và người
        // đọc phải suy ra chiều từ mũi tên.
        //
        // Mức chênh của một tỷ lệ là ĐIỂM phần trăm, không phải phần trăm: 93% xuống
        // 91% là giảm 2 điểm phần trăm chứ không phải giảm 2%. Vì thế không dùng
        // style "percent" ở đây — số đã được nhân 100 sẵn và đơn vị nằm trong nhãn.
        signedPercentagePoints: {
          signDisplay: "exceptZero",
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        },
        signedCount: {
          signDisplay: "exceptZero",
          maximumFractionDigits: 0,
        },
        signedDays: {
          signDisplay: "exceptZero",
          maximumFractionDigits: 2,
        },
      },
    },
  };
});
