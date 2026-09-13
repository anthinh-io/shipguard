import { test, expect } from "@playwright/test";

import { mockSession } from "./session";

// Trình duyệt gọi thẳng backend (ADR-0002), nên mẫu chặn phải bám địa chỉ backend chứ
// không phải địa chỉ của trang.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const DASHBOARD_API = `${BACKEND_URL}/dashboard**`;

test.beforeEach(async ({ context }) => {
  await context.addCookies([
    { name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" },
  ]);
  await mockSession(context);
});

function bodyFor(deliveredOrders: number) {
  return {
    reporting_period: { start_date: "2018-01-01", end_date: "2018-01-30" },
    filter_options: { customer_states: ["AL", "MA"] },
    kpis: {
      delivered_orders: deliveredOrders,
      late_orders: deliveredOrders > 0 ? 10 : 0,
      on_time_rate: deliveredOrders > 0 ? 0.9 : null,
      payment_approval: { median_days: 0.01, p90_days: 1.44 },
      seller_handling: { median_days: 1.82, p90_days: 5.99 },
      carrier_transit: { median_days: 7.1, p90_days: 18.9 },
      late_related_low_review_rate: deliveredOrders > 0 ? 0.32 : null,
    },
    late_rate_trend: { granularity: "day", points: [] },
    late_rate_by_state:
      deliveredOrders > 0
        ? [
            {
              customer_state: "AL",
              delivered_orders: deliveredOrders,
              late_orders: 10,
              late_rate: 0.1,
            },
          ]
        : [],
  };
}

test("chọn một bang thì sinh đúng một lần gọi mới và màn hình đổi theo", async ({
  page,
}) => {
  const calls: string[] = [];
  await page.route(DASHBOARD_API, (route) => {
    const url = new URL(route.request().url());
    calls.push(url.search);
    const state = url.searchParams.get("customer_state");
    return route.fulfill({ json: bodyFor(state === "AL" ? 397 : 75548) });
  });

  await page.goto("/");
  await expect(page.getByTestId("kpi-grid")).toBeVisible();
  expect(calls).toHaveLength(1);

  await page.getByTestId("filter-customer-state").click();
  await page.getByRole("option", { name: "AL" }).click();

  // Đổi bộ lọc chỉ tốn đúng một lần gọi mới.
  await expect.poll(() => calls.length).toBe(2);
  expect(calls[1]).toContain("customer_state=AL");
  // Màn hình đổi theo: ô đơn đã giao hiện đúng con số ứng với bang AL.
  await expect(page.getByTestId("kpi-on-time-rate")).toContainText("397");
});

test("xoá hết đưa mọi bộ lọc về mặc định trong một thao tác", async ({ page }) => {
  const calls: string[] = [];
  await page.route(DASHBOARD_API, (route) => {
    const url = new URL(route.request().url());
    calls.push(url.search);
    const hasFilter = url.searchParams.has("customer_state");
    return route.fulfill({ json: bodyFor(hasFilter ? 397 : 75548) });
  });

  await page.goto("/");
  await page.getByTestId("filter-customer-state").click();
  await page.getByRole("option", { name: "AL" }).click();
  await expect.poll(() => calls.length).toBe(2);

  await page.getByTestId("filter-clear-all").click();

  // Một thao tác duy nhất phải xoá cả bộ lọc bang lẫn khoảng thời gian đã chọn, sinh
  // đúng một lần gọi mới không mang tham số nào.
  await expect.poll(() => calls.length).toBe(3);
  expect(calls[2]).toBe("");
});

test("bộ lọc không ra đơn nào thì hiện thông báo rỗng, không phải thông báo lỗi", async ({
  page,
}) => {
  await page.route(DASHBOARD_API, (route) => route.fulfill({ json: bodyFor(0) }));

  await page.goto("/");

  await expect(page.getByTestId("dashboard-empty")).toBeVisible();
  await expect(page.getByTestId("dashboard-error")).toHaveCount(0);
  await expect(page.getByTestId("kpi-grid")).toHaveCount(0);
  // Thanh bộ lọc vẫn còn đó để người dùng nới lại điều kiện.
  await expect(page.getByTestId("filter-bar")).toBeVisible();
});
