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
      },
    },
  };
});
