import { cookies } from "next/headers";

import { AppHeader } from "@/app/components/app-header";
import { AppSidebar } from "@/app/components/app-sidebar";
import { AuthGate } from "@/app/components/auth-gate";
import { ProfileProvider } from "@/app/components/profile-provider";
import { SidebarInset, SidebarProvider } from "@/app/components/ui/sidebar";
import { TooltipProvider } from "@/app/components/ui/tooltip";

// Mọi trang cần đăng nhập nằm trong group này, nên trang mới thêm vào tự được chặn và tự
// có sidebar mà không phải nhớ gắn riêng. /login nằm ngoài group: không cổng chặn, không
// khung ứng dụng.
export default async function AppLayout({ children }: LayoutProps<"/">) {
  // SidebarProvider tự ghi cookie này mỗi lần thu gọn/mở rộng; đọc lại ở máy chủ để lần
  // tải đầu vẽ đúng trạng thái thay vì nháy từ mở sang thu gọn.
  const defaultOpen = (await cookies()).get("sidebar_state")?.value !== "false";

  return (
    // Cổng chặn bọc ngoài cả khung: chưa xác nhận phiên thì sidebar và ProfileProvider
    // (cùng lời gọi /me của nó) chưa được vẽ.
    <AuthGate>
      <ProfileProvider>
        {/* Tooltip của mục sidebar khi thu gọn thành dải icon cần provider này. */}
        <TooltipProvider>
          <SidebarProvider defaultOpen={defaultOpen}>
            <AppSidebar />
            <SidebarInset>
              <AppHeader />
              {children}
            </SidebarInset>
          </SidebarProvider>
        </TooltipProvider>
      </ProfileProvider>
    </AuthGate>
  );
}
