"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { hasAccessToken, refreshAccessToken } from "@/app/lib/api";
import { loginPathForCurrentPage } from "@/app/lib/next-path";

// Chặn ở client chứ không ở máy chủ Next: access token chỉ nằm trong bộ nhớ trình duyệt,
// máy chủ Next không có cách nào biết người đang mở trang là ai (ADR-0006).
export function AuthGate({ children }: { children: ReactNode }) {
  const t = useTranslations("auth");
  const router = useRouter();
  // Vừa đăng nhập xong rồi chuyển trang phía client thì token đã có sẵn — không làm mới
  // thêm lần nữa. Tải trang đầy đủ thì bộ nhớ trống, luôn bắt đầu từ "checking".
  const [authenticated, setAuthenticated] = useState(hasAccessToken);

  useEffect(() => {
    if (authenticated) {
      return;
    }
    let cancelled = false;
    refreshAccessToken().then((ok) => {
      if (cancelled) {
        return;
      }
      if (ok) {
        setAuthenticated(true);
      } else {
        router.replace(loginPathForCurrentPage());
      }
    });
    return () => {
      cancelled = true;
    };
  }, [authenticated, router]);

  if (!authenticated) {
    // Không vẽ children trong nhịp chờ: vẽ ra rồi mới chuyển đi là nháy nội dung, và
    // Dashboard sẽ kịp gọi máy chủ khi chưa có token.
    return (
      <p
        data-testid="auth-checking"
        className="mx-auto w-full max-w-5xl px-4 py-8 opacity-70"
      >
        {t("checking")}
      </p>
    );
  }
  return children;
}
