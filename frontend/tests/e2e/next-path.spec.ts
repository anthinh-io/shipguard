import { test, expect } from "@playwright/test";

import { loginPathFor, safeNextPath } from "../../app/lib/next-path";

// Không mở trình duyệt: đây là hàm thuần, và là chốt duy nhất đứng giữa một đường liên
// kết do người ngoài soạn với lệnh chuyển trang sau đăng nhập.
test("đường dẫn nội bộ đi qua nguyên vẹn, kể cả chuỗi truy vấn và neo", () => {
  expect(safeNextPath("/")).toBe("/");
  expect(safeNextPath("/orders?page=2#x")).toBe("/orders?page=2#x");
});

test("không có next thì về trang chủ", () => {
  expect(safeNextPath(null)).toBe("/");
  expect(safeNextPath("")).toBe("/");
});

// Mỗi dòng là một cách trình duyệt hiểu thành "sang host khác": `//` là địa chỉ không
// giao thức, `\` được chuẩn hoá thành `/`, tab bị bỏ đi trước khi phân tích, còn `.`
// và `..` bị gỡ khỏi đường dẫn và để lộ ra `//` ngay sau khi phân tích.
for (const external of [
  "https://evil.example",
  "//evil.example",
  "/\\evil.example",
  "/\t/evil.example",
  "javascript:alert(1)",
  "/.//evil.example",
  "/..//evil.example",
  "/%2e//evil.example",
]) {
  test(`không bao giờ chuyển ra ngoài: ${JSON.stringify(external)}`, () => {
    expect(safeNextPath(external)).toBe("/");
  });
}

test("không quay vòng về chính trang đăng nhập", () => {
  expect(safeNextPath("/login?next=/x")).toBe("/");
});

test("đường dẫn đăng nhập mang theo trang đang mở", () => {
  expect(loginPathFor("/?from=colleague")).toBe("/login?next=%2F%3Ffrom%3Dcolleague");
});
