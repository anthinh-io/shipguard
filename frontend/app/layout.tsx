import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getLocale } from "next-intl/server";
import { ThemeProvider } from "next-themes";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ShipGuard",
  description: "ShipGuard: Delivery Performance Intelligence",
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const locale = await getLocale();

  return (
    // suppressHydrationWarning là bắt buộc: next-themes gắn lớp chủ đề vào <html> bằng
    // script chạy trước khi React nhận trang, nên markup máy chủ và trình duyệt lệch
    // nhau đúng ở thẻ này. Chỉ thẻ này, không lan xuống các thẻ con.
    <html
      lang={locale}
      className={`${geistSans.variable} ${geistMono.variable}`}
      suppressHydrationWarning
    >
      <body>
        {/* Provider không nhận props: render từ Server Component thì next-intl tự lấy
            locale, messages và formats từ i18n/request.ts. */}
        <NextIntlClientProvider>
          {/* Chế độ tối bám theo cài đặt hệ điều hành y như trước, chỉ khác là chạy bằng
              lớp .dark thay cho prefers-color-scheme — shadcn viết cứng tên lớp này trong
              chart.tsx nên media query không dùng được. Chưa có nút cho người dùng chọn. */}
          <ThemeProvider
            attribute="class"
            defaultTheme="system"
            enableSystem
            disableTransitionOnChange
          >
            {children}
          </ThemeProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
