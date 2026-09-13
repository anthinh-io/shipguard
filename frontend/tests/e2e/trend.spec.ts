import { test, expect, type Page } from "@playwright/test";

import { mockSession } from "./session";

// Trình duyệt gọi thẳng backend (ADR-0002), nên mẫu chặn phải bám địa chỉ backend chứ
// không phải địa chỉ của trang.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const DASHBOARD_API = `${BACKEND_URL}/dashboard**`;

// Ghim ngôn ngữ ở tiếng Việt, cùng quy ước với smoke.spec.ts.
test.beforeEach(async ({ context }) => {
  await context.addCookies([
    { name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" },
  ]);
  await mockSession(context);
});

function fulfillWith(page: Page, granularity: "day" | "week" | "month") {
  return page.route(DASHBOARD_API, (route) =>
    route.fulfill({
      json: {
        reporting_period: { start_date: "2018-01-01", end_date: "2018-01-30" },
        filter_options: { customer_states: ["AL", "MA"] },
        kpis: {
          delivered_orders: 100,
          late_orders: 10,
          on_time_rate: 0.9,
          payment_approval: { median_days: 0.01, p90_days: 1.44 },
          seller_handling: { median_days: 1.82, p90_days: 5.99 },
          carrier_transit: { median_days: 7.1, p90_days: 18.9 },
          late_related_low_review_rate: 0.32,
        },
        late_rate_trend: {
          granularity,
          points: [
            {
              bucket_start: "2018-01-01",
              delivered_orders: 50,
              late_orders: 5,
              late_rate: 0.1,
            },
            {
              bucket_start: "2018-01-08",
              delivered_orders: 50,
              late_orders: 5,
              late_rate: 0.1,
            },
          ],
        },
      },
    }),
  );
}

// Ranh giới 31 ngày và ngưỡng tuần/tháng được quyết định và kiểm ở tầng tính toán của
// backend (backend/tests/test_dashboard_service.py). Bài test này kiểm phần thuộc về
// frontend: bảng điều khiển hiển thị đúng độ mịn mà backend trả về, không tự suy ra
// hay ghi đè — đúng tiêu chí "Frontend không chứa logic chọn độ mịn".
for (const granularity of ["day", "week", "month"] as const) {
  test(`biểu đồ xu hướng hiển thị đúng độ mịn "${granularity}" mà máy chủ trả về`, async ({
    page,
  }) => {
    await fulfillWith(page, granularity);

    await page.goto("/");

    await expect(page.getByTestId("late-rate-trend")).toHaveAttribute(
      "data-granularity",
      granularity,
    );
  });
}

// Cùng một quy tắc chọn độ mịn với backend (day < 31 ngày, week < 183 ngày, else
// month), lặp lại ở đây chỉ để tính tham số truy vấn thật sự đi ra từ lịch — độ chính
// xác của chính ranh giới đã ghim ở hai bài test backend nói trên.
function chooseGranularity(startISO: string, endISO: string): "day" | "week" | "month" {
  const start = new Date(startISO);
  const end = new Date(endISO);
  const spanDays = Math.round((end.getTime() - start.getTime()) / 86_400_000) + 1;
  if (spanDays < 31) return "day";
  if (spanDays < 183) return "week";
  return "month";
}

async function mockGranularityAwareDashboard(page: Page) {
  await page.route(DASHBOARD_API, (route) => {
    const url = new URL(route.request().url());
    const start = url.searchParams.get("start_date");
    const end = url.searchParams.get("end_date");
    const granularity =
      start && end ? chooseGranularity(start, end) : ("month" as const);
    return route.fulfill({
      json: {
        reporting_period: {
          start_date: start ?? "2017-09-01",
          end_date: end ?? "2018-08-31",
        },
        filter_options: { customer_states: ["AL"] },
        kpis: {
          delivered_orders: 100,
          late_orders: 10,
          on_time_rate: 0.9,
          payment_approval: { median_days: 0.01, p90_days: 1.44 },
          seller_handling: { median_days: 1.82, p90_days: 5.99 },
          carrier_transit: { median_days: 7.1, p90_days: 18.9 },
          late_related_low_review_rate: 0.32,
        },
        late_rate_trend: { granularity, points: [] },
        late_rate_by_state: [
          {
            customer_state: "AL",
            delivered_orders: 100,
            late_orders: 10,
            late_rate: 0.1,
          },
        ],
      },
    });
  });
}

// Bấm tới ngày `target` trên lịch thật, bấm nút tháng sau tối đa vài lần nếu ngày đó
// chưa nằm trong hai tháng đang hiện — Calendar mở mặc định ở tháng hiện tại, còn kỳ
// cần chọn tính từ "hôm nay" nên có thể rơi ra ngoài khung hai tháng ban đầu.
async function clickDay(page: Page, target: Date) {
  const locator = page.locator(`[data-slot="calendar"] [data-day="${target.toLocaleDateString()}"]`);
  for (let attempt = 0; attempt < 3 && (await locator.count()) === 0; attempt++) {
    await page.locator(".rdp-button_next").first().click();
  }
  await locator.click();
}

test("chọn khoảng ngày thật trên lịch làm độ mịn chuyển đúng khi vượt ranh giới 31 ngày", async ({
  page,
}) => {
  await mockGranularityAwareDashboard(page);
  await page.goto("/");
  await expect(page.getByTestId("late-rate-trend")).toHaveAttribute(
    "data-granularity",
    "month",
  );

  const today = new Date();
  const dayMs = 24 * 60 * 60 * 1000;

  // Kỳ 11 ngày — rõ ràng dưới ranh giới 31 ngày.
  await page.getByTestId("filter-date-range").click();
  await clickDay(page, today);
  await clickDay(page, new Date(today.getTime() + 10 * dayMs));
  await expect(page.getByTestId("late-rate-trend")).toHaveAttribute(
    "data-granularity",
    "day",
  );

  // Nới ra 41 ngày — vượt hẳn ranh giới 31 ngày, còn cách xa ranh giới 6 tháng.
  await page.getByTestId("filter-date-range").click();
  await clickDay(page, today);
  await clickDay(page, new Date(today.getTime() + 40 * dayMs));
  await expect(page.getByTestId("late-rate-trend")).toHaveAttribute(
    "data-granularity",
    "week",
  );
});
