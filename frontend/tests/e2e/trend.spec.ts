import { test, expect, type Page } from "@playwright/test";

// Trình duyệt gọi thẳng backend (ADR-0002), nên mẫu chặn phải bám địa chỉ backend chứ
// không phải địa chỉ của trang.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const DASHBOARD_API = `${BACKEND_URL}/dashboard**`;

// Ghim ngôn ngữ ở tiếng Việt, cùng quy ước với smoke.spec.ts.
test.beforeEach(async ({ context }) => {
  await context.addCookies([
    { name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" },
  ]);
});

function fulfillWith(page: Page, granularity: "day" | "week" | "month") {
  return page.route(DASHBOARD_API, (route) =>
    route.fulfill({
      json: {
        reporting_period: { start_date: "2018-01-01", end_date: "2018-01-30" },
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
// hay ghi đè — đúng tiêu chí "Frontend không chứa logic chọn độ mịn". Việc chuyển độ
// mịn khi người dùng thật sự đổi khoảng thời gian được phủ ở filters.spec.ts (#11),
// nơi bộ chọn ngày mới tồn tại.
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
