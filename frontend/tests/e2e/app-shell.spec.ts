import { test, expect, type BrowserContext } from "@playwright/test";

import { mockMe, switchLanguage } from "./session";

// Trình duyệt gọi thẳng backend (ADR-0006), nên mẫu chặn phải bám địa chỉ backend chứ
// không phải địa chỉ của trang.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const DASHBOARD_API = `${BACKEND_URL}/dashboard**`;

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

// Phiên giả lập mà bài test tắt được: sau khi đăng xuất, /auth/refresh trả 401 y như
// backend thật với cookie đã bị thu hồi.
async function mockSessionWithLogout(context: BrowserContext) {
  const session = { active: true, logouts: 0 };
  await context.route(`${BACKEND_URL}/auth/refresh`, (route) =>
    session.active
      ? route.fulfill({ json: { access_token: "t", token_type: "bearer" } })
      : route.fulfill({ status: 401, json: { detail: "Invalid refresh token" } }),
  );
  await context.route(`${BACKEND_URL}/auth/logout`, (route) => {
    session.active = false;
    session.logouts += 1;
    return route.fulfill({ status: 204 });
  });
  await mockMe(context);
  await context.route(DASHBOARD_API, (route) => route.fulfill({ json: DASHBOARD_BODY }));
  return session;
}

test.beforeEach(async ({ context }) => {
  await context.addCookies([
    { name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" },
  ]);
});

test("đã đăng nhập thì thấy sidebar với mục Bảng điều khiển, tên và vai trò ở đáy", async ({
  page,
  context,
}) => {
  await mockSessionWithLogout(context);

  await page.goto("/");

  await expect(page.getByTestId("nav-dashboard")).toContainText("Bảng điều khiển");
  await expect(page.getByTestId("user-name")).toHaveText("Nguyễn Lan");
  await expect(page.getByTestId("user-role")).toHaveText("Nhân viên vận hành");
  // Nút đổi ngôn ngữ chỉ còn trong menu người dùng, không còn ở đầu trang.
  await expect(page.getByTestId("kpi-grid")).toBeVisible();
  await expect(page.getByTestId("language-toggle")).toHaveCount(0);
});

test("thu gọn sidebar thành dải icon thì tải lại trang vẫn thu gọn", async ({
  page,
  context,
}) => {
  await mockSessionWithLogout(context);
  await page.goto("/");
  const sidebar = page.locator('[data-slot="sidebar"]');
  await expect(sidebar).toHaveAttribute("data-state", "expanded");

  await page.getByTestId("sidebar-trigger").click();
  await expect(sidebar).toHaveAttribute("data-state", "collapsed");

  await page.reload();

  await expect(page.getByTestId("kpi-grid")).toBeVisible();
  await expect(sidebar).toHaveAttribute("data-state", "collapsed");
});

test("màn hình hẹp thì sidebar ẩn, nút menu mở nó ra dạng ngăn kéo", async ({
  page,
  context,
}) => {
  await mockSessionWithLogout(context);
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto("/");

  await expect(page.getByTestId("kpi-grid")).toBeVisible();
  await expect(page.getByTestId("nav-dashboard")).toBeHidden();
  const content = await page.locator('[data-slot="sidebar-inset"]').boundingBox();
  expect(content?.x).toBe(0);
  expect(content?.width).toBe(390);

  await page.getByTestId("sidebar-trigger").click();

  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();
  await expect(drawer.getByTestId("nav-dashboard")).toBeVisible();
});

test("đổi ngôn ngữ từ menu ở đáy sidebar thì cả trang đổi theo", async ({
  page,
  context,
}) => {
  await mockSessionWithLogout(context);
  await page.goto("/");
  await expect(page.getByTestId("kpi-late-orders")).toContainText("Đơn giao trễ");

  await switchLanguage(page);

  await expect(page.getByTestId("kpi-late-orders")).toContainText("Late orders");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByTestId("user-role")).toHaveText("Operations Staff");
});

test("đăng xuất thì về trang đăng nhập, tải lại hay bấm Back cũng không vào lại được", async ({
  page,
  context,
}) => {
  const session = await mockSessionWithLogout(context);
  await page.goto("/");
  await expect(page.getByTestId("kpi-grid")).toBeVisible();
  await page.goto("/?view=2");
  await expect(page.getByTestId("kpi-grid")).toBeVisible();

  await page.getByTestId("user-menu").click();
  await page.getByTestId("user-menu-logout").click();

  await expect(page).toHaveURL("/login");
  expect(session.logouts).toBe(1);

  await page.reload();
  await expect(page).toHaveURL("/login");
  await expect(page.getByTestId("login-form")).toBeVisible();

  // Trang /?view=2 đã bị thay bằng /login; lùi một bước là về / trong lịch sử.
  await page.goBack();
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByTestId("login-form")).toBeVisible();
  await expect(page.getByTestId("kpi-grid")).toHaveCount(0);
});

test("đăng xuất không tới được máy chủ thì báo lỗi, vẫn ở lại phiên và thử lại được", async ({
  page,
  context,
}) => {
  const session = await mockSessionWithLogout(context);
  // Cookie refresh chưa bị thu hồi: coi như đã đăng xuất là người sau mở lại ứng dụng trên
  // máy dùng chung sẽ vào thẳng phiên này. Lần đầu mất mạng, lần sau rơi về route của
  // helper (route đăng ký sau được hỏi trước).
  let attempts = 0;
  await context.route(`${BACKEND_URL}/auth/logout`, (route) => {
    attempts += 1;
    return attempts === 1 ? route.abort() : route.fallback();
  });
  await page.goto("/");
  await expect(page.getByTestId("kpi-grid")).toBeVisible();

  await page.getByTestId("user-menu").click();
  await page.getByTestId("user-menu-logout").click();

  await expect(page.getByTestId("logout-error")).toContainText("Chưa đăng xuất được");
  await expect(page).toHaveURL("/");
  await expect(page.getByTestId("kpi-grid")).toBeVisible();
  expect(session.active).toBe(true);

  await page.getByTestId("user-menu-logout").click();

  await expect(page).toHaveURL("/login");
  expect(session.logouts).toBe(1);
  await page.reload();
  await expect(page).toHaveURL("/login");
});
