import { loginPathForCurrentPage } from "./next-path";

// Phải đọc nguyên dạng tĩnh như thế này thì Next mới thay được giá trị lúc build.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

// Access token chỉ nằm trong bộ nhớ (ADR-0006): tải lại trang là mất, và mỗi lần tải
// trang lấy lại qua /auth/refresh bằng cookie httpOnly mà JavaScript không đọc được.
let accessToken: string | null = null;

// Refresh token chỉ dùng được một lần — lần làm mới thứ hai bằng cùng cookie nhận 401.
// Nên mọi nơi cần làm mới cùng lúc (Strict Mode gắn cổng chặn hai lần, bảng điều khiển
// và ô gợi ý cùng gặp 401) phải chờ chung một lời gọi, không thì tự đá người dùng ra.
let pendingRefresh: Promise<boolean> | null = null;

type TokenResponse = { access_token: string };

async function storeToken(response: Response) {
  accessToken = ((await response.json()) as TokenResponse).access_token;
}

export function hasAccessToken(): boolean {
  return accessToken !== null;
}

export function refreshAccessToken(): Promise<boolean> {
  pendingRefresh ??= requestRefresh().finally(() => {
    pendingRefresh = null;
  });
  return pendingRefresh;
}

async function requestRefresh(): Promise<boolean> {
  try {
    // credentials "include" vì frontend và backend khác cổng: thiếu nó thì trình duyệt
    // không gửi cookie refresh, cũng không nhận cookie mới xoay vòng về.
    const response = await fetch(`${BACKEND_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (!response.ok) {
      return false;
    }
    await storeToken(response);
    return true;
  } catch {
    // Không tới được máy chủ thì cũng không xác nhận được phiên; trang đăng nhập là nơi
    // người dùng thấy lỗi kết nối rõ ràng.
    return false;
  }
}

export type LoginResult = "ok" | "invalid" | "unreachable";

export async function login(email: string, password: string): Promise<LoginResult> {
  let response: Response;
  try {
    response = await fetch(`${BACKEND_URL}/auth/login`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  } catch {
    return "unreachable";
  }
  if (response.status === 401) {
    return "invalid";
  }
  if (!response.ok) {
    return "unreachable";
  }
  await storeToken(response);
  return "ok";
}

export async function logout(): Promise<void> {
  try {
    await fetch(`${BACKEND_URL}/auth/logout`, { method: "POST", credentials: "include" });
  } catch {
    // Không tới được máy chủ thì cookie chưa bị thu hồi, nhưng vẫn rời phiên ở trình duyệt
    // này: giữ người dùng lại vì một lỗi mạng còn tệ hơn trên máy dùng chung.
  }
  accessToken = null;
}

function withToken(init: RequestInit | undefined): RequestInit {
  const headers = new Headers(init?.headers);
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  return { ...init, headers };
}

function redirectToLogin() {
  window.location.replace(loginPathForCurrentPage());
}

// Cùng chữ ký với fetch để chỗ gọi chỉ đổi tên hàm. Gặp 401 thì làm mới đúng một lần rồi
// thử lại; vẫn không được thì về trang đăng nhập và trả nguyên phản hồi cho bên gọi — bên
// gọi xử lý nó như mọi phản hồi lỗi khác trong nhịp trang đang chuyển đi.
export async function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(url, withToken(init));
  if (response.status !== 401) {
    return response;
  }
  if (!(await refreshAccessToken())) {
    redirectToLogin();
    return response;
  }
  const retried = await fetch(url, withToken(init));
  if (retried.status === 401) {
    redirectToLogin();
  }
  return retried;
}

export type ChangePasswordResult = "ok" | "wrongCurrent" | "tooShort" | "unreachable";

// Máy chủ báo lý do bằng mã trạng thái; chuỗi detail tiếng Anh chỉ dành cho log, còn câu
// người dùng đọc lấy từ messages/*.json theo khóa trả về ở đây.
export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<ChangePasswordResult> {
  let response: Response;
  try {
    response = await apiFetch(`${BACKEND_URL}/auth/password`, {
      method: "POST",
      // Phản hồi đặt cookie refresh mới cho phiên này (mọi cookie cũ đã bị thu hồi); thiếu
      // credentials thì trình duyệt bỏ cookie đó và lần tải lại sau bị đá ra.
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
  } catch {
    return "unreachable";
  }
  if (response.status === 400) {
    return "wrongCurrent";
  }
  if (response.status === 422) {
    return "tooShort";
  }
  if (!response.ok) {
    return "unreachable";
  }
  await storeToken(response);
  return "ok";
}
