"use client";

import { useTransition } from "react";
import { useLocale, useTranslations } from "next-intl";

import { setUserLocale } from "@/i18n/locale";
import { Button } from "./ui/button";

// Dùng chung cho nút ở trang đăng nhập và mục trong menu người dùng ở đáy sidebar.
export function useLocaleSwitch() {
  const locale = useLocale();
  const [isPending, startTransition] = useTransition();

  // Server action ghi cookie rồi Next trả về giao diện đã cập nhật trong cùng một vòng
  // gọi. Cây component không bị tháo ra nên trạng thái của Dashboard còn nguyên và không
  // sinh thêm lần gọi máy chủ nào.
  function switchLocale() {
    startTransition(async () => {
      try {
        await setUserLocale(locale === "vi" ? "en" : "vi");
      } catch {
        // Ghi cookie hỏng thì giữ nguyên ngôn ngữ đang dùng. Để lỗi lọt ra khỏi
        // transition sẽ kích error boundary và xoá cả bảng điều khiển đang hiện —
        // mất số liệu đã tải vì một việc chẳng liên quan gì tới số liệu.
      }
    });
  }

  return { isPending, switchLocale };
}

export default function LanguageToggle() {
  const t = useTranslations("language");
  const { isPending, switchLocale } = useLocaleSwitch();

  return (
    <Button
      data-testid="language-toggle"
      variant="outline"
      size="sm"
      // Nhãn trên nút là ngôn ngữ sẽ chuyển sang, không phải ngôn ngữ đang dùng. Đọc
      // riêng một mình thì "English" không nói rõ là đang ở đâu và sẽ đi đâu, nên câu
      // đầy đủ nằm ở aria-label cho trình đọc màn hình.
      aria-label={t("switchLabel")}
      disabled={isPending}
      onClick={switchLocale}
    >
      {t("switchTo")}
    </Button>
  );
}
