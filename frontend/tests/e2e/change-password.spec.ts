import { test, expect, type Page } from "@playwright/test";

import { mockSession, switchLanguage } from "./session";

// Trình duyệt gọi thẳng backend (ADR-0006), nên mẫu chặn phải bám địa chỉ backend chứ
// không phải địa chỉ của trang.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const DASHBOARD_API = `${BACKEND_URL}/dashboard**`;
const PASSWORD_API = `${BACKEND_URL}/auth/password`;

// Luôn giả lập /auth/password: đổi mật khẩu thật của Super Admin sẽ làm hỏng signInForReal
// ở mọi lần chạy sau. Luồng thật (mật khẩu mới dùng được, phiên khác bị thu hồi) nằm ở
// backend/tests/test_auth_routes.py.
const DASHBOARD_BODY = {
  reporting_period: { start_date: "2018-01-01", end_date: "2018-01-30" },
  filter_options: { customer_states: ["AL", "MA"] },
  kpis: {
    delivered_orders: 75548,
    late_orders: 10,
    on_time_rate: 0.9,
    payment_approval: { median_days: 0.01, p90_days: 1.44 },
    seller_handling: { median_days: 1.82, p90_days: 5.99 },
    carrier_transit: { median_days: 7.1, p90_days: 18.9 },
    late_related_low_review_rate: 0.32,
  },
  late_rate_trend: { granularity: "day", points: [] },
  late_rate_by_state: [
    { customer_state: "AL", delivered_orders: 75548, late_orders: 10, late_rate: 0.1 },
  ],
  small_sample: false,
  comparison_period: null,
  comparison_kpis: null,
  comparison_late_rate_trend: null,
};

test.beforeEach(async ({ context }) => {
  await context.addCookies([
    { name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" },
  ]);
  await mockSession(context);
});

async function openDialog(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("kpi-grid")).toBeVisible();
  await page.getByTestId("user-menu").click();
  await page.getByTestId("user-menu-change-password").click();
  await expect(page.getByTestId("change-password-dialog")).toBeVisible();
}

async function fillDialog(page: Page, current: string, next: string, confirm = next) {
  await page.getByTestId("change-password-current").fill(current);
  await page.getByTestId("change-password-new").fill(next);
  await page.getByTestId("change-password-confirm").fill(confirm);
  await page.getByTestId("change-password-submit").click();
}

test("đổi thành công thì báo đã đổi và ở lại phiên bằng token mới", async ({ page }) => {
  const authorizations: string[] = [];
  await page.route(DASHBOARD_API, (route) => {
    authorizations.push(route.request().headers()["authorization"]);
    return route.fulfill({ json: DASHBOARD_BODY });
  });
  const bodies: unknown[] = [];
  await page.route(PASSWORD_API, (route) => {
    bodies.push(route.request().postDataJSON());
    return route.fulfill({ json: { access_token: "after-change", token_type: "bearer" } });
  });

  await openDialog(page);
  await fillDialog(page, "correct-horse-battery", "staple-battery-horse");

  await expect(page.getByTestId("change-password-success")).toContainText(
    "Đã đổi mật khẩu",
  );
  // Ô nhập lại chỉ kiểm ở client, không gửi lên máy chủ.
  expect(bodies).toEqual([
    { current_password: "correct-horse-battery", new_password: "staple-battery-horse" },
  ]);

  await page.getByRole("button", { name: "Đóng" }).click();
  await expect(page.getByTestId("change-password-dialog")).toHaveCount(0);
  await page.getByTestId("filter-customer-state").click();
  await page.getByRole("option", { name: "AL" }).click();

  await expect.poll(() => authorizations.at(-1)).toBe("Bearer after-change");
  // Vẫn ở bảng điều khiển, không bị đưa về /login; bộ lọc vừa chọn nằm trên URL (#24).
  await expect(page).toHaveURL("/?customer_state=AL");
});

for (const { status, detail, message } of [
  { status: 400, detail: "Current password is incorrect", message: "Mật khẩu hiện tại không đúng." },
  {
    status: 422,
    detail: "Password must be at least 8 characters",
    message: "Mật khẩu mới phải có ít nhất 8 ký tự.",
  },
]) {
  test(`máy chủ từ chối với mã ${status} thì báo rõ lý do bằng ngôn ngữ đang dùng`, async ({
    page,
  }) => {
    await page.route(DASHBOARD_API, (route) => route.fulfill({ json: DASHBOARD_BODY }));
    await page.route(PASSWORD_API, (route) => route.fulfill({ status, json: { detail } }));

    await openDialog(page);
    await fillDialog(page, "whatever-password", "short-or-not");

    await expect(page.getByTestId("change-password-error")).toHaveText(message);
    await expect(page.getByTestId("change-password-success")).toHaveCount(0);
    await expect(page.getByTestId("change-password-dialog")).toBeVisible();
    // 400 không bị hiểu nhầm là phiên hết hạn: người dùng vẫn ở bảng điều khiển.
    await expect(page).toHaveURL("/");
  });
}

test("hai lần nhập mật khẩu mới lệch nhau thì báo ngay và không gửi đi", async ({ page }) => {
  await page.route(DASHBOARD_API, (route) => route.fulfill({ json: DASHBOARD_BODY }));
  let calls = 0;
  await page.route(PASSWORD_API, (route) => {
    calls += 1;
    return route.fulfill({ json: { access_token: "x", token_type: "bearer" } });
  });

  await openDialog(page);
  await fillDialog(page, "correct-horse-battery", "staple-battery-horse", "staple-battery-hose");

  await expect(page.getByTestId("change-password-error")).toHaveText(
    "Hai lần nhập mật khẩu mới không khớp.",
  );
  expect(calls).toBe(0);
});

test("hộp thoại đổi mật khẩu song ngữ", async ({ page }) => {
  await page.route(DASHBOARD_API, (route) => route.fulfill({ json: DASHBOARD_BODY }));
  await page.goto("/");
  await switchLanguage(page);
  await expect(page.getByTestId("kpi-late-orders")).toContainText("Late orders");

  await page.getByTestId("user-menu").click();
  await page.getByTestId("user-menu-change-password").click();

  const dialog = page.getByTestId("change-password-dialog");
  await expect(dialog.getByRole("heading", { name: "Change password" })).toBeVisible();
  await expect(dialog).toContainText("Repeat new password");
  await expect(dialog.getByRole("button", { name: "Cancel" })).toBeVisible();
});
