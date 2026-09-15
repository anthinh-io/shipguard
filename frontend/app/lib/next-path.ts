// Origin giả chỉ để phân tích: so origin sau khi phân tích thay vì soi chuỗi bằng tay, vì
// bộ phân tích URL chuẩn hoá `\` và bỏ tab y như trình duyệt sẽ làm lúc chuyển trang —
// soi tay thì luôn sót một biến thể của `//host`.
const PARSE_ORIGIN = "http://shipguard.invalid";

export const LOGIN_PATH = "/login";

// `next` đến từ chuỗi truy vấn, tức là ai cũng soạn được. Chỉ nhận đường dẫn trong ứng
// dụng; mọi thứ khác về trang chủ.
export function safeNextPath(raw: string | null): string {
  if (!raw?.startsWith("/")) {
    return "/";
  }
  const url = new URL(raw, PARSE_ORIGIN);
  // Kiểm cả pathname sau khi phân tích: `/.//evil.example` giữ nguyên origin giả, nhưng
  // gỡ `.` xong thì còn lại `//evil.example` — trình duyệt đọc thành một host khác.
  if (
    url.origin !== PARSE_ORIGIN ||
    url.pathname.startsWith("//") ||
    url.pathname === LOGIN_PATH
  ) {
    return "/";
  }
  return `${url.pathname}${url.search}${url.hash}`;
}

export function loginPathFor(current: string): string {
  return `${LOGIN_PATH}?next=${encodeURIComponent(current)}`;
}

// Giữ cả neo: đường liên kết đồng nghiệp gửi có thể trỏ tới một mục trong trang.
export function loginPathForCurrentPage(): string {
  const { pathname, search, hash } = window.location;
  return loginPathFor(`${pathname}${search}${hash}`);
}
