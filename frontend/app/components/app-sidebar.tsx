"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { Gauge, LayoutDashboard, Package, UsersRound } from "lucide-react";

import { NavUser } from "./nav-user";
import type { Role } from "@/app/lib/users-api";
import { useProfile } from "./profile-provider";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "./ui/sidebar";

type NavItem = {
  href: string;
  labelKey: "dashboard" | "orders" | "modelMetrics" | "admin";
  icon: typeof LayoutDashboard;
  // Không khai là mọi vai trò đều thấy. Ẩn mục chỉ là tiện cho người dùng — máy chủ vẫn tự
  // kiểm vai trò ở từng lời gọi.
  roles?: readonly Role[];
};

// Mục theo vai trò vẫn nằm trong mảng: AppHeader tra tiêu đề trang từ đây, lọc bỏ khỏi mảng
// thì trang mất tiêu đề. Chỉ lọc lúc vẽ sidebar.
export const NAV_ITEMS: readonly NavItem[] = [
  { href: "/", labelKey: "dashboard", icon: LayoutDashboard },
  { href: "/orders", labelKey: "orders", icon: Package },
  { href: "/model-metrics", labelKey: "modelMetrics", icon: Gauge },
  {
    href: "/admin/users",
    labelKey: "admin",
    icon: UsersRound,
    roles: ["logistics_manager", "super_admin"],
  },
];

export function AppSidebar() {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const profile = useProfile();
  // Hồ sơ chưa tải xong thì ẩn mục theo vai trò: hiện rồi rút lại trông như lỗi.
  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.roles || (profile !== null && item.roles.includes(profile.role)),
  );

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <span className="truncate px-2 text-lg font-semibold group-data-[collapsible=icon]:hidden">
          ShipGuard
        </span>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarMenu>
            {visibleItems.map((item) => (
              <SidebarMenuItem key={item.href}>
                <SidebarMenuButton
                  asChild
                  isActive={pathname === item.href}
                  tooltip={t(item.labelKey)}
                >
                  <Link href={item.href} data-testid={`nav-${item.labelKey}`}>
                    <item.icon />
                    <span>{t(item.labelKey)}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
