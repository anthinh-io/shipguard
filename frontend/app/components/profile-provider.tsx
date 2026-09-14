"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { apiFetch } from "@/app/lib/api";

// Phải đọc nguyên dạng tĩnh như thế này thì Next mới thay được giá trị lúc build.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

export type Role = "operations_staff" | "logistics_manager" | "super_admin";

export type Profile = {
  id: number;
  email: string;
  display_name: string;
  role: Role;
};

const ProfileContext = createContext<Profile | null>(null);

// Hỏi /me một lần cho cả khung ứng dụng: menu người dùng cần tên, sidebar cần vai trò, trang
// quản trị cần id của chính mình. Hỏi /me thay vì đọc access token vì tên hiển thị không
// nằm trong token, và vai trò trong token có thể lệch hiện trạng tới 15 phút.
export function ProfileProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<Profile | null>(null);

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
        // Thiếu hồ sơ thì tên ở đáy sidebar trống và mục theo vai trò ẩn đi; mọi trang vẫn
        // dùng được, và máy chủ vẫn tự kiểm quyền ở từng lời gọi.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return <ProfileContext value={profile}>{children}</ProfileContext>;
}

// null trong nhịp đang tải hoặc khi không lấy được hồ sơ.
export function useProfile(): Profile | null {
  return useContext(ProfileContext);
}
