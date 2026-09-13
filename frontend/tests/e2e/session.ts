import { existsSync } from "node:fs";
import path from "node:path";

import { expect, type BrowserContext } from "@playwright/test";

// Trình duyệt gọi thẳng backend (ADR-0006), nên mẫu chặn phải bám địa chỉ backend chứ
// không phải địa chỉ của trang.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

// Cho spec giả lập /dashboard: cổng chặn chỉ cần /auth/refresh trả một token bất kỳ, vì
// mọi lời gọi số liệu phía sau cũng bị chặn lại và không bao giờ tới backend thật.
export async function mockSession(context: BrowserContext) {
  await context.route(`${BACKEND_URL}/auth/refresh`, (route) =>
    route.fulfill({ json: { access_token: "test-access-token", token_type: "bearer" } }),
  );
}

// Cho spec gọi backend thật: token giả sẽ nhận 401 từ /dashboard. Đăng nhập thật bằng
// Super Admin trong .env gốc; context.request dùng chung kho cookie với trình duyệt, nên
// trang tự làm mới phiên bằng cookie thật y như người dùng tải lại trang.
export async function signInForReal(context: BrowserContext) {
  // Máy không có .env gốc (CI chẳng hạn) thì đặt thẳng hai biến vào môi trường; có tệp
  // thì loadEnvFile cũng không ghi đè biến đã đặt sẵn.
  const envFile = path.join(__dirname, "..", "..", "..", ".env");
  if (existsSync(envFile)) {
    process.loadEnvFile(envFile);
  }
  const response = await context.request.post(`${BACKEND_URL}/auth/login`, {
    data: {
      email: process.env.SUPER_ADMIN_EMAIL,
      password: process.env.SUPER_ADMIN_PASSWORD,
    },
  });
  expect(
    response.ok(),
    `Đăng nhập Super Admin thất bại (${response.status()}): kiểm tra backend đang chạy và ` +
      "SUPER_ADMIN_EMAIL / SUPER_ADMIN_PASSWORD trong .env gốc khớp tài khoản trong cơ sở " +
      "dữ liệu — mật khẩu đổi bằng script đặt lại thì .env không tự đổi theo.",
  ).toBe(true);
}
