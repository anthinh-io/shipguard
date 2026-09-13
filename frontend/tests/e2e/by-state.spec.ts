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

// Thứ tự xếp hạng (bang trễ nhất lên đầu) là quyết định của backend — service layer
// đã kiểm điều đó (test_state_distribution_covers_27_states). Bài test này kiểm phần
// thuộc về frontend: biểu đồ vẽ đúng thứ tự mảng nhận được, không tự sắp xếp lại và
// không đổi thành bản đồ.
test("biểu đồ theo bang hiển thị đúng thứ tự xếp hạng từ cao xuống thấp, không dùng bản đồ", async ({
  page,
}) => {
  await page.route(DASHBOARD_API, (route) =>
    route.fulfill({
      json: {
        reporting_period: { start_date: "2018-01-01", end_date: "2018-01-30" },
        filter_options: { customer_states: ["AL", "MA", "SE"] },
        kpis: {
          delivered_orders: 100,
          late_orders: 10,
          on_time_rate: 0.9,
          payment_approval: { median_days: 0.01, p90_days: 1.44 },
          seller_handling: { median_days: 1.82, p90_days: 5.99 },
          carrier_transit: { median_days: 7.1, p90_days: 18.9 },
          late_related_low_review_rate: 0.32,
        },
        late_rate_trend: { granularity: "day", points: [] },
        late_rate_by_state: [
          { customer_state: "AL", delivered_orders: 397, late_orders: 85, late_rate: 0.2141 },
          { customer_state: "MA", delivered_orders: 717, late_orders: 125, late_rate: 0.1743 },
          { customer_state: "SE", delivered_orders: 335, late_orders: 51, late_rate: 0.1522 },
        ],
      },
    }),
  );

  await page.goto("/");

  const chart = page.getByTestId("late-rate-by-state");
  await expect(chart).toBeVisible();
  // Là biểu đồ cột: có các hình chữ nhật recharts vẽ cột, không có lớp SVG nào của
  // bản đồ (recharts không có thành phần bản đồ, nên sự có mặt của .recharts-bar là
  // đủ để khẳng định đây là biểu đồ cột).
  await expect(chart.locator(".recharts-bar-rectangle").first()).toBeVisible();

  // Thứ tự nhãn trục dọc phải khớp đúng thứ tự mảng nhận được: AL, MA, SE — bang trễ
  // nhất lên trước, không bị vẽ lại theo alphabet hay theo một quy tắc nào khác.
  // recharts vẽ nhãn trục trong một lớp riêng (.recharts-yAxis-tick-labels), tách
  // khỏi nhóm <g> của chính trục (.recharts-yAxis chỉ chứa vạch chia).
  const tickLabels = chart.locator(
    ".recharts-yAxis-tick-labels .recharts-cartesian-axis-tick-value",
  );
  await expect(tickLabels).toHaveText(["AL", "MA", "SE"]);
});
