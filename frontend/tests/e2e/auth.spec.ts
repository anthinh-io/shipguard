import { test, expect, type BrowserContext, type Page } from "@playwright/test";

import { mockMe } from "./session";

// Trình duyệt gọi thẳng backend (ADR-0006), nên mẫu chặn phải bám địa chỉ backend chứ
// không phải địa chỉ của trang.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const DASHBOARD_API = `${BACKEND_URL}/dashboard**`;
const REFRESH_API = `${BACKEND_URL}/auth/refresh`;
const LOGIN_API = `${BACKEND_URL}/auth/login`;

test.beforeEach(async ({ context }) => {
  await context.addCookies([
    { name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" },
  ]);
  // Mọi bài ở đây tự giả lập /auth/refresh; vào được bảng điều khiển thì sidebar hỏi /me.
  await mockMe(context);
});

function bodyFor(deliveredOrders: number) {
  return {
    reporting_period: { start_date: "2018-01-01", end_date: "2018-01-30" },
    filter_options: { customer_states: ["AL", "MA"] },
    kpis: {
      delivered_orders: deliveredOrders,
      late_orders: 10,
      on_time_rate: 0.9,
      payment_approval: { median_days: 0.01, p90_days: 1.44 },
      seller_handling: { median_days: 1.82, p90_days: 5.99 },
      carrier_transit: { median_days: 7.1, p90_days: 18.9 },
      late_related_low_review_rate: 0.32,
    },
    late_rate_trend: { granularity: "day", points: [] },
    late_rate_by_state: [
      { customer_state: "AL", delivered_orders: deliveredOrders, late_orders: 10, late_rate: 0.1 },
    ],
    small_sample: false,
    comparison_period: null,
    comparison_kpis: null,
    comparison_late_rate_trend: null,
  };
}

// Chưa có phiên: cookie refresh không có hoặc đã hết hạn, backend trả 401.
async function mockNoSession(context: BrowserContext) {
  const calls = { refresh: 0, dashboard: 0 };
  await context.route(REFRESH_API, (route) => {
    calls.refresh += 1;
    return route.fulfill({ status: 401, json: { detail: "Invalid refresh token" } });
  });
  await context.route(DASHBOARD_API, (route) => {
    calls.dashboard += 1;
    return route.fulfill({ json: bodyFor(75548) });
  });
  return calls;
}

async function submitLogin(page: Page) {
  await page.getByTestId("login-email").fill("lan@shipguard.vn");
  await page.getByTestId("login-password").fill("correct-horse-battery");
  await page.getByTestId("login-submit").click();
}

test("chưa đăng nhập mở bảng điều khiển thì được đưa tới trang đăng nhập", async ({
  page,
  context,
}) => {
  const calls = await mockNoSession(context);

  await page.goto("/");

  await expect(page).toHaveURL("/login?next=%2F");
  await expect(page.getByTestId("login-form")).toBeVisible();
  await expect(page.getByTestId("filter-bar")).toHaveCount(0);
  // Không một lời gọi số liệu nào đi ra khi chưa biết người dùng là ai.
  expect(calls.dashboard).toBe(0);
});

test("đăng nhập từ đường liên kết được gửi thì quay lại đúng trang đó", async ({
  page,
  context,
}) => {
  const calls = await mockNoSession(context);
  await context.route(LOGIN_API, (route) =>
    route.fulfill({ json: { access_token: "fresh-token", token_type: "bearer" } }),
  );

  await page.goto("/?from=colleague#by-state");
  await expect(page).toHaveURL("/login?next=%2F%3Ffrom%3Dcolleague%23by-state");

  await submitLogin(page);

  await expect(page).toHaveURL("/?from=colleague#by-state");
  await expect(page.getByTestId("kpi-grid")).toBeVisible();
  // Token vừa cấp nằm sẵn trong bộ nhớ; làm mới thêm lần nữa là phí một lần xoay vòng.
  expect(calls.refresh).toBe(1);
});

test("tải lại trang vẫn còn phiên, và trong lúc chờ không nháy nội dung", async ({
  page,
  context,
}) => {
  const calls = { refresh: 0 };
  await context.route(REFRESH_API, async (route) => {
    calls.refresh += 1;
    // Giữ lại một nhịp để trạng thái chờ quan sát được một cách tất định.
    await new Promise((resolve) => setTimeout(resolve, 1000));
    await route.fulfill({ json: { access_token: "t", token_type: "bearer" } });
  });
  await context.route(DASHBOARD_API, (route) => route.fulfill({ json: bodyFor(75548) }));

  await page.goto("/");

  await expect(page.getByTestId("auth-checking")).toBeVisible();
  await expect(page.getByTestId("filter-bar")).toHaveCount(0);
  await expect(page.getByTestId("kpi-grid")).toBeVisible();
  // Strict Mode gắn cổng chặn hai lần, nhưng refresh token chỉ dùng được một lần: hai
  // lời gọi sẽ làm lời gọi thứ hai trả 401 và đá người dùng ra ngoài.
  expect(calls.refresh).toBe(1);

  await page.reload();

  await expect(page.getByTestId("kpi-grid")).toBeVisible();
  await expect(page).toHaveURL("/");
  expect(calls.refresh).toBe(2);
});

test("phiên ngắn hạn hết hạn giữa chừng thì số liệu vẫn tải được", async ({
  page,
  context,
}) => {
  const calls = { refresh: 0 };
  let expired = false;
  await context.route(REFRESH_API, (route) => {
    calls.refresh += 1;
    return route.fulfill({
      json: { access_token: `t${calls.refresh}`, token_type: "bearer" },
    });
  });
  await context.route(DASHBOARD_API, (route) => {
    const request = route.request();
    if (expired && request.headers()["authorization"] === "Bearer t1") {
      return route.fulfill({ status: 401, json: { detail: "Not authenticated" } });
    }
    const state = new URL(request.url()).searchParams.get("customer_state");
    return route.fulfill({ json: bodyFor(state === "AL" ? 397 : 75548) });
  });

  await page.goto("/");
  await expect(page.getByTestId("kpi-grid")).toBeVisible();

  expired = true;
  await page.getByTestId("filter-customer-state").click();
  await page.getByRole("option", { name: "AL" }).click();

  await expect(page.getByTestId("kpi-on-time-rate")).toContainText("397");
  await expect(page.getByTestId("dashboard-error")).toHaveCount(0);
  // Vẫn ở bảng điều khiển, không bị đưa về /login; bộ lọc vừa chọn nằm trên URL (#24).
  await expect(page).toHaveURL("/?customer_state=AL");
  expect(calls.refresh).toBe(2);
});

test("nhập sai thông tin thì thấy thông báo chung và vẫn ở trang đăng nhập", async ({
  page,
  context,
}) => {
  await mockNoSession(context);
  await context.route(LOGIN_API, (route) =>
    route.fulfill({ status: 401, json: { detail: "Invalid email or password" } }),
  );

  await page.goto("/login");
  await submitLogin(page);

  await expect(page.getByTestId("login-error")).toContainText(
    "Email hoặc mật khẩu không đúng",
  );
  await expect(page).toHaveURL("/login");
});

test("next trỏ ra trang ngoài thì đăng nhập xong vẫn ở trong ứng dụng", async ({
  page,
  context,
}) => {
  await mockNoSession(context);
  await context.route(LOGIN_API, (route) =>
    route.fulfill({ json: { access_token: "fresh-token", token_type: "bearer" } }),
  );

  await page.goto("/login?next=%2F%2Fevil.example");
  await submitLogin(page);

  await expect(page).toHaveURL("http://localhost:3000/");
  await expect(page.getByTestId("kpi-grid")).toBeVisible();
});

test("trang đăng nhập song ngữ và không có khung của bảng điều khiển", async ({
  page,
  context,
}) => {
  await mockNoSession(context);
  await context.addCookies([
    { name: "NEXT_LOCALE", value: "en", url: "http://localhost:3000" },
  ]);

  await page.goto("/login");

  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expect(page.getByTestId("language-toggle")).toBeVisible();

  await page.getByTestId("language-toggle").click();

  await expect(page.getByRole("heading", { name: "Đăng nhập" })).toBeVisible();
  await expect(page.getByTestId("filter-bar")).toHaveCount(0);
});
