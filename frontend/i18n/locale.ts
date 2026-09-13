"use server";

import { cookies } from "next/headers";

import { LOCALE_COOKIE, isLocale, type Locale } from "./config";

// Chỉ hàm ghi mới là server action. Hàm đọc nằm trong request.ts, không xuất ra ngoài —
// mỗi hàm xuất từ một tệp "use server" là một điểm gọi được từ mạng.
export async function setUserLocale(locale: Locale) {
  // Kiểu dữ liệu chỉ ràng buộc được các chỗ gọi trong mã này; hàm còn gọi được từ mạng
  // với bất kỳ giá trị nào, nên phải chặn lại trước khi ghi.
  if (!isLocale(locale)) {
    return;
  }
  (await cookies()).set(LOCALE_COOKIE, locale, {
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
    sameSite: "lax",
  });
}
