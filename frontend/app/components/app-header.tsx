"use client";

import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";

import { NAV_ITEMS } from "./app-sidebar";
import { SidebarTrigger } from "./ui/sidebar";

// Nút menu nằm ở khung chứ không ở từng trang: trên màn hình hẹp đây là lối duy nhất mở
// sidebar, trang nào quên gắn là người dùng kẹt lại.
export function AppHeader() {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const current = NAV_ITEMS.find((item) => item.href === pathname);

  return (
    <header className="flex h-12 items-center gap-2 border-b px-4">
      <SidebarTrigger data-testid="sidebar-trigger" />
      {current ? <h1 className="text-lg font-semibold">{t(current.labelKey)}</h1> : null}
    </header>
  );
}
