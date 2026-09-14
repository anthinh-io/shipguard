"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { ChevronsUpDown, CircleUser, KeyRound, Languages, LogOut } from "lucide-react";

import { apiFetch, logout } from "@/app/lib/api";
import { ChangePasswordDialog } from "./change-password-dialog";
import { useLocaleSwitch } from "./language-toggle";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import { SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "./ui/sidebar";

// Phải đọc nguyên dạng tĩnh như thế này thì Next mới thay được giá trị lúc build.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

type Profile = {
  display_name: string;
  role: "operations_staff" | "logistics_manager" | "super_admin";
};

export function NavUser() {
  const t = useTranslations("userMenu");
  const tRole = useTranslations("roles");
  const tLanguage = useTranslations("language");
  const { isPending, switchLocale } = useLocaleSwitch();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [changingPassword, setChangingPassword] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [signOutFailed, setSignOutFailed] = useState(false);

  // Hỏi /me thay vì đọc access token: tên hiển thị không nằm trong token, và vai trò
  // trong token có thể lệch hiện trạng tới 15 phút.
  useEffect(() => {
    let cancelled = false;
    apiFetch(`${BACKEND_URL}/me`)
      .then((response) => (response.ok ? (response.json() as Promise<Profile>) : null))
      .then((body) => {
        if (!cancelled) {
          setProfile(body);
        }
      })
      .catch(() => {
        // Thiếu tên ở đáy sidebar không chặn việc gì khác; menu vẫn dùng được.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleLogout() {
    setSigningOut(true);
    setSignOutFailed(false);
    if (await logout()) {
      // Tải trang đầy đủ chứ không chuyển trang phía client: bỏ sạch bộ nhớ JavaScript
      // (token, số liệu đã tải), và replace để trang vừa rời không nằm trong lịch sử.
      window.location.replace("/login");
      return;
    }
    setSigningOut(false);
    setSignOutFailed(true);
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu
          onOpenChange={(open) => {
            if (!open) {
              setSignOutFailed(false);
            }
          }}
        >
          {/* Nút không đặt aria-label: nó sẽ đè tên và vai trò, thứ trình đọc màn hình cần
              đọc ra. */}
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton size="lg" data-testid="user-menu">
              <CircleUser />
              <span className="grid flex-1 text-left leading-tight">
                <span data-testid="user-name" className="truncate font-medium">
                  {profile?.display_name}
                </span>
                <span data-testid="user-role" className="truncate text-xs opacity-70">
                  {profile ? tRole(profile.role) : null}
                </span>
              </span>
              <ChevronsUpDown className="ml-auto" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="top" align="start">
            <DropdownMenuItem
              data-testid="user-menu-change-password"
              onSelect={() => setChangingPassword(true)}
            >
              <KeyRound />
              {t("changePassword")}
            </DropdownMenuItem>
            <DropdownMenuItem
              data-testid="user-menu-language"
              aria-label={tLanguage("switchLabel")}
              disabled={isPending}
              onSelect={switchLocale}
            >
              <Languages />
              {tLanguage("switchTo")}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              data-testid="user-menu-logout"
              disabled={signingOut}
              onSelect={(event) => {
                // Giữ menu mở: nếu máy chủ không xác nhận, thông báo lỗi phải hiện ngay
                // dưới mục người dùng vừa bấm, không biến mất cùng menu.
                event.preventDefault();
                void handleLogout();
              }}
            >
              <LogOut />
              {signingOut ? t("signingOut") : t("logout")}
            </DropdownMenuItem>
            {signOutFailed ? (
              <p
                data-testid="logout-error"
                role="alert"
                className="max-w-56 px-1.5 py-1 text-sm text-red-700 dark:text-red-400"
              >
                {t("logoutFailed")}
              </p>
            ) : null}
          </DropdownMenuContent>
        </DropdownMenu>
        {/* Dialog nằm ngoài DropdownMenu: menu đóng lại khi chọn mục, dialog đặt bên trong
            sẽ bị tháo theo. */}
        <ChangePasswordDialog open={changingPassword} onOpenChange={setChangingPassword} />
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
