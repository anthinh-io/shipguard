import { test, expect, type Page } from "@playwright/test";

// Trình duyệt gọi thẳng backend (ADR-0002), nên mẫu chặn phải bám địa chỉ backend chứ
// không phải địa chỉ của trang.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const DASHBOARD_API = `${BACKEND_URL}/dashboard**`;
const SELLERS_API = `${BACKEND_URL}/sellers**`;

test.beforeEach(async ({ context }) => {
  await context.addCookies([
    { name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" },
  ]);
});

function points(rates: (number | null)[], startDay: number) {
  return rates.map((late_rate, index) => ({
    bucket_start: `2018-01-${String(startDay + index).padStart(2, "0")}`,
    delivered_orders: late_rate === null ? 0 : 100,
    late_orders: late_rate === null ? 0 : Math.round(late_rate * 100),
    late_rate,
  }));
}

function kpis(onTimeRate: number | null, lateOrders: number, median: number | null) {
  return {
    delivered_orders: onTimeRate === null ? 0 : 500,
    late_orders: lateOrders,
    on_time_rate: onTimeRate,
    payment_approval: { median_days: median, p90_days: median },
    seller_handling: { median_days: median, p90_days: median },
    carrier_transit: { median_days: median, p90_days: median },
    late_related_low_review_rate: onTimeRate === null ? null : 0.32,
  };
}

type Options = { comparison: boolean; emptyComparison?: boolean };

function bodyFor({ comparison, emptyComparison }: Options) {
  return {
    reporting_period: { start_date: "2018-01-01", end_date: "2018-01-03" },
    filter_options: { customer_states: ["AL", "SP"] },
    // Kỳ đang xem: đúng hạn 91%, trung vị 2 ngày.
    kpis: kpis(0.91, 45, 2),
    late_rate_trend: { granularity: "day", points: points([0.1, 0.2, 0.15], 1) },
    late_rate_by_state: [
      {
        customer_state: "SP",
        delivered_orders: 500,
        late_orders: 45,
        late_rate: 0.09,
      },
    ],
    small_sample: false,
    comparison_period: comparison
      ? { start_date: "2017-12-29", end_date: "2017-12-31" }
      : null,
    // Kỳ đối chiếu rỗng vẫn là một khối đầy đủ, chỉ toàn 0 và null — đây là trường hợp
    // xảy ra thật với bộ Olist ở đầu dải dữ liệu.
    comparison_kpis: comparison
      ? emptyComparison
        ? kpis(null, 0, null)
        : kpis(0.93, 60, 1.5)
      : null,
    comparison_late_rate_trend: comparison
      ? {
          granularity: "day",
          points: emptyComparison
            ? points([null, null, null], 1)
            : points([0.07, 0.08, 0.05], 1),
        }
      : null,
  };
}

async function mock(page: Page): Promise<string[]> {
  const calls: string[] = [];
  await page.route(SELLERS_API, (route) => route.fulfill({ json: [] }));
  await page.route(DASHBOARD_API, (route) => {
    const url = new URL(route.request().url());
    calls.push(url.search);
    const mode = url.searchParams.get("comparison");
    return route.fulfill({ json: bodyFor({ comparison: mode === "previous" }) });
  });
  return calls;
}

function lines(page: Page) {
  return page.locator('[data-testid="late-rate-trend"] .recharts-line');
}

test("tắt so sánh thì một đường và không có mức chênh nào", async ({ page }) => {
  await mock(page);

  await page.goto("/");
  await expect(page.getByTestId("kpi-grid")).toBeVisible();

  await expect(lines(page)).toHaveCount(1);
  await expect(page.getByTestId("kpi-delta")).toHaveCount(0);
});

test("bật so sánh thì ô KPI hiện mức chênh và biểu đồ có hai đường", async ({
  page,
}) => {
  const calls = await mock(page);

  await page.goto("/");
  await expect(page.getByTestId("kpi-grid")).toBeVisible();
  expect(calls).toHaveLength(1);

  await page.getByTestId("filter-comparison").click();
  await page.getByRole("option", { name: "Kỳ liền trước" }).click();

  // Cả hai khối về trong cùng một lần gọi — tiêu chí của #13.
  await expect.poll(() => calls.length).toBe(2);
  expect(calls[1]).toContain("comparison=previous");

  await expect(lines(page)).toHaveCount(2);

  // Đúng hạn 91% so với 93% là giảm 2 điểm phần trăm: xấu đi, nên mũi tên đi xuống.
  const onTime = page.getByTestId("kpi-on-time-rate").getByTestId("kpi-delta");
  await expect(onTime).toBeVisible();
  await expect(onTime).toContainText("2,00");
  await expect(onTime).toContainText("điểm phần trăm");
  await expect(onTime).toHaveAttribute("data-direction", "down");

  // Đơn trễ 45 so với 60 là giảm 15 đơn — cùng chiều mũi tên, khác đơn vị hẳn.
  const late = page.getByTestId("kpi-late-orders").getByTestId("kpi-delta");
  await expect(late).toContainText("15");
  await expect(late).toHaveAttribute("data-direction", "down");

  // Chặng thời gian chênh nhau theo ngày, không phải điểm phần trăm.
  const stage = page.getByTestId("kpi-payment-approval").getByTestId("kpi-delta");
  await expect(stage).toContainText("ngày");
  await expect(stage).toHaveAttribute("data-direction", "up");
});

test("kỳ đối chiếu không có dữ liệu thì không vỡ và không hiện mức chênh", async ({
  page,
}) => {
  await page.route(SELLERS_API, (route) => route.fulfill({ json: [] }));
  await page.route(DASHBOARD_API, (route) =>
    route.fulfill({
      json: bodyFor({ comparison: true, emptyComparison: true }),
    }),
  );

  await page.goto("/");

  // Màn hình vẫn đứng: lưới KPI, số liệu kỳ chính và cả hai biểu đồ còn nguyên.
  await expect(page.getByTestId("kpi-grid")).toBeVisible();
  await expect(page.getByTestId("kpi-on-time-rate")).toContainText("91");
  await expect(page.getByTestId("late-rate-by-state")).toBeVisible();
  await expect(page.getByTestId("dashboard-error")).toHaveCount(0);
  await expect(page.getByTestId("dashboard-empty")).toHaveCount(0);
  // Không có vế đối chiếu thì không có mức chênh — rỗng, không phải "0".
  await expect(page.getByTestId("kpi-delta")).toHaveCount(0);
});

test("xoá hết bộ lọc tắt luôn chế độ so sánh", async ({ page }) => {
  const calls = await mock(page);

  await page.goto("/");
  await page.getByTestId("filter-comparison").click();
  await page.getByRole("option", { name: "Kỳ liền trước" }).click();
  await expect.poll(() => calls.length).toBe(2);

  await page.getByTestId("filter-clear-all").click();

  await expect.poll(() => calls.length).toBe(3);
  expect(calls[2]).toBe("");
  await expect(lines(page)).toHaveCount(1);
});
