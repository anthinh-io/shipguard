import type { Role } from "@/app/components/profile-provider";
import { apiFetch } from "./api";

// Phải đọc nguyên dạng tĩnh như thế này thì Next mới thay được giá trị lúc build.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

export type AdminUser = {
  id: number;
  email: string;
  display_name: string;
  role: Role;
  is_locked: boolean;
};

// Không có super_admin: máy chủ từ chối gán vai trò đó, nên giao diện cũng không đưa ra.
export const ASSIGNABLE_ROLES = ["operations_staff", "logistics_manager"] as const;
export type AssignableRole = (typeof ASSIGNABLE_ROLES)[number];

export type ListUsersResult =
  { kind: "ok"; users: AdminUser[] } | { kind: "forbidden" } | { kind: "error" };

// 403 là câu trả lời của máy chủ cho người không đủ vai trò — trang dựa vào nó để từ chối,
// không tự đoán từ hồ sơ, vì máy chủ mới là nơi quyết định.
export async function listUsers(): Promise<ListUsersResult> {
  try {
    const response = await apiFetch(`${BACKEND_URL}/users`, { cache: "no-store" });
    if (response.status === 403) {
      return { kind: "forbidden" };
    }
    if (!response.ok) {
      return { kind: "error" };
    }
    return { kind: "ok", users: (await response.json()) as AdminUser[] };
  } catch {
    return { kind: "error" };
  }
}

export type NewUser = {
  display_name: string;
  email: string;
  role: AssignableRole;
  password: string;
};

export type CreateUserFailure = "emailTaken" | "invalidEmail" | "tooShort" | "unreachable";

type ValidationDetail = { loc: (string | number)[] }[];

// Máy chủ báo lý do bằng mã trạng thái; chuỗi detail tiếng Anh chỉ dành cho log, còn câu
// người dùng đọc lấy từ messages/*.json theo khóa trả về ở đây.
export async function createUser(
  input: NewUser,
): Promise<{ kind: "ok"; user: AdminUser } | { kind: CreateUserFailure }> {
  let response: Response;
  try {
    response = await apiFetch(`${BACKEND_URL}/users`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
  } catch {
    return { kind: "unreachable" };
  }
  if (response.status === 409) {
    return { kind: "emailTaken" };
  }
  if (response.status === 422) {
    // 422 do Pydantic trả detail dạng mảng kèm vị trí trường lỗi; 422 do chính sách mật
    // khẩu trả detail là một chuỗi.
    const { detail } = (await response.json()) as { detail: string | ValidationDetail };
    const emailInvalid =
      Array.isArray(detail) && detail.some((error) => error.loc.includes("email"));
    return { kind: emailInvalid ? "invalidEmail" : "tooShort" };
  }
  if (!response.ok) {
    return { kind: "unreachable" };
  }
  return { kind: "ok", user: (await response.json()) as AdminUser };
}

// null cho mọi kiểu thất bại: menu thao tác chỉ có một thông báo lỗi chung, vì các lý do máy
// chủ từ chối (Super Admin, chính mình) đã bị ẩn khỏi menu từ trước.
export async function updateUser(
  id: number,
  patch: { role?: AssignableRole; is_locked?: boolean },
): Promise<AdminUser | null> {
  try {
    const response = await apiFetch(`${BACKEND_URL}/users/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    return response.ok ? ((await response.json()) as AdminUser) : null;
  } catch {
    return null;
  }
}

export type ResetUserPasswordResult = "ok" | "tooShort" | "unreachable";

export async function resetUserPassword(
  id: number,
  newPassword: string,
): Promise<ResetUserPasswordResult> {
  let response: Response;
  try {
    response = await apiFetch(`${BACKEND_URL}/users/${id}/password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_password: newPassword }),
    });
  } catch {
    return "unreachable";
  }
  if (response.status === 422) {
    return "tooShort";
  }
  return response.ok ? "ok" : "unreachable";
}
