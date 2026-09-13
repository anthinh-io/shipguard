import { AuthGate } from "@/app/components/auth-gate";

// Mọi trang cần đăng nhập nằm trong group này, nên trang mới thêm vào tự được chặn mà
// không phải nhớ gắn riêng. /login nằm ngoài group: không cổng chặn, không khung ứng dụng.
export default function AppLayout({ children }: LayoutProps<"/">) {
  return <AuthGate>{children}</AuthGate>;
}
