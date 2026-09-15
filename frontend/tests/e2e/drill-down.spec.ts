import { test, expect, type Locator, type Page } from "@playwright/test";

import { mockSession } from "./session";

// Trình duyệt gọi thẳng backend (ADR-0002), nên mẫu chặn phải bám địa chỉ backend chứ
// không phải địa chỉ của trang.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const DASHBOARD_API = `${BACKEND_URL}/dashboard**`;
const ORDERS_API = `${BACKEND_URL}/orders**`;
const SELLERS_API = `${BACKEND_URL}/sellers**`;

const SELLER_ID = "6560211a19b47992c3666cc44a7e94c0";

// Số khớp giữa điểm được click và danh sách mở ra đã chứng minh ở backend
// (test_drill_down_contract.py). Ở đây chỉ kiểm phần của frontend: đường liên kết mang
// đúng bộ lọc, gợi ý và con trỏ, Back về nguyên bảng điều khiển.
const DASHBOARD_QUERY = `?start_date=2018-01-03&end_date=2018-01-15&customer_state=SP&seller_id=${SELLER_ID}&comparison=previous`;

test.beforeEach(async ({ context }) => {
  await context.addCookies([
    { name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" },
  ]);
  await mockSession(context);
  // Trang Đơn hàng tải danh sách bang và tra nhãn người bán khi mở. Không giả lập thì
  // token giả tới backend thật nhận 401, và apiFetch đưa cả trang về /login.
  await context.route(`${BACKEND_URL}/customer-states`, (route) =>
    route.fulfill({ json: ["AL", "MA", "SP"] }),
  );
  await context.route(SELLERS_API, (route) =>
    route.fulfill({
      json: [
        { seller_id: SELLER_ID, seller_city: "curitiba", seller_state: "PR", delivered_orders: 42 },
      ],
    }),
  );
});

function kpis() {
  return {
    delivered_orders: 500,
    late_orders: 45,
    on_time_rate: 0.91,
    payment_approval: { median_days: 0.01, p90_days: 1.44 },
    seller_handling: { median_days: 1.82, p90_days: 5.99 },
    carrier_transit: { median_days: 7.1, p90_days: 18.9 },
    late_related_low_review_rate: 0.32,
  };
}

// Nhóm tuần đầu bị kẹp từ thứ Hai 01/01 về thứ Tư 03/01, nhóm cuối chỉ còn một ngày —
// đúng hình dạng backend trả cho một kỳ bắt đầu và kết thúc giữa tuần.
const WEEKLY_POINTS = [
  { bucket_start: "2018-01-01", bucket_from: "2018-01-03", bucket_to: "2018-01-07" },
  { bucket_start: "2018-01-08", bucket_from: "2018-01-08", bucket_to: "2018-01-14" },
  { bucket_start: "2018-01-15", bucket_from: "2018-01-15", bucket_to: "2018-01-15" },
].map((bounds, index) => ({
  ...bounds,
  delivered_orders: 100,
  late_orders: 10 + index,
  late_rate: 0.1 + index / 100,
}));

const FILTERED_BODY = {
  reporting_period: { start_date: "2018-01-03", end_date: "2018-01-15" },
  filter_options: { customer_states: ["AL", "MA", "SP"] },
  kpis: kpis(),
  late_rate_trend: { granularity: "week", points: WEEKLY_POINTS },
  late_rate_by_state: [
    { customer_state: "SP", delivered_orders: 300, late_orders: 33, late_rate: 0.11 },
  ],
  small_sample: false,
  comparison_period: { start_date: "2017-12-21", end_date: "2018-01-02" },
  comparison_kpis: kpis(),
  // Kỳ đối chiếu có khoảng riêng; không được lọt sang đường liên kết.
  comparison_late_rate_trend: {
    granularity: "week",
    // Tỷ lệ khác hẳn kỳ chính để chấm của hai đường không chồng lên nhau.
    points: WEEKLY_POINTS.map((point) => ({
      ...point,
      late_rate: point.late_rate + 0.2,
      bucket_start: "2017-12-18",
      bucket_from: "2017-12-21",
      bucket_to: "2017-12-24",
    })),
  },
};

// Không truyền kỳ nào: reporting_period của phản hồi là kỳ mặc định do backend giải.
const DEFAULT_PERIOD_BODY = {
  ...FILTERED_BODY,
  reporting_period: { start_date: "2017-09-01", end_date: "2018-08-31" },
  filter_options: { customer_states: ["AL", "MA"] },
  late_rate_trend: { granularity: "month", points: [] },
  late_rate_by_state: [
    { customer_state: "AL", delivered_orders: 397, late_orders: 85, late_rate: 0.2141 },
    { customer_state: "MA", delivered_orders: 717, late_orders: 125, late_rate: 0.1743 },
  ],
  comparison_period: null,
  comparison_kpis: null,
  comparison_late_rate_trend: null,
};

async function mockBackend(page: Page, body: unknown): Promise<string[]> {
  const orderCalls: string[] = [];
  await page.route(DASHBOARD_API, (route) => route.fulfill({ json: body }));
  await page.route(ORDERS_API, (route) => {
    orderCalls.push(new URL(route.request().url()).search);
    return route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 50 } });
  });
  return orderCalls;
}

// Chấm của đường kỳ đang xem; đường nét đứt của kỳ đối chiếu vẽ sau nó. recharts 3 vẽ
// chấm ở lớp riêng, không nằm trong .recharts-line.
function trendDot(page: Page, index: number): Locator {
  return page
    .getByTestId("late-rate-trend")
    .locator(".recharts-line-dots")
    .first()
    .locator(".recharts-dot")
    .nth(index);
}

function stateBar(page: Page, index: number): Locator {
  return page.getByTestId("late-rate-by-state").locator(".recharts-bar-rectangle").nth(index);
}

function queryOf(page: Page): Record<string, string> {
  return Object.fromEntries(new URL(page.url()).searchParams);
}

// Rê tới, đợi gợi ý hiện, rồi mới nhấn chuột tại chỗ — như người dùng thật. recharts chỉ
// biết điểm nào đang được trỏ qua mousemove (gộp theo khung hình); với locator.click(),
// cú bấm tới tay recharts khi chưa có điểm nào đang trỏ và không đi đâu cả. Gợi ý hiện ra
// là dấu hiệu recharts đã nhận điểm.
async function pointAndClick(page: Page, target: Locator, chartTestId: string) {
  await target.hover();
  await expect(tooltipOf(page, chartTestId)).toContainText("Xem đơn trễ");
  await page.mouse.down();
  await page.mouse.up();
}

function tooltipOf(page: Page, chartTestId: string): Locator {
  return page.getByTestId(chartTestId).locator(".recharts-tooltip-wrapper");
}

test("rê chuột lên điểm xu hướng hay cột bang thì con trỏ thành bàn tay và có gợi ý", async ({
  page,
}) => {
  await mockBackend(page, FILTERED_BODY);
  await page.goto(`/${DASHBOARD_QUERY}`);

  const trend = page.getByTestId("late-rate-trend");
  await expect(trend.locator(".recharts-wrapper")).toHaveCSS("cursor", "pointer");
  await trendDot(page, 1).hover();
  await expect(tooltipOf(page, "late-rate-trend")).toContainText("Xem đơn trễ");

  const byState = page.getByTestId("late-rate-by-state");
  await expect(byState.locator(".recharts-wrapper")).toHaveCSS("cursor", "pointer");
  await stateBar(page, 0).hover();
  await expect(tooltipOf(page, "late-rate-by-state")).toContainText("SP");
  await expect(tooltipOf(page, "late-rate-by-state")).toContainText("Xem đơn trễ");
});

test("click điểm xu hướng mở đơn trễ trong đúng khoảng của điểm, giữ bang và người bán, bỏ kỳ so sánh", async ({
  page,
}) => {
  const orderCalls = await mockBackend(page, FILTERED_BODY);
  await page.goto(`/${DASHBOARD_QUERY}`);

  await pointAndClick(page, trendDot(page, 0), "late-rate-trend");

  await page.waitForURL(/\/orders\?/);
  const expected = {
    delivery_outcome: "late",
    delivered_from: "2018-01-03",
    delivered_to: "2018-01-07",
    customer_state: "SP",
    seller_id: SELLER_ID,
  };
  expect(queryOf(page)).toEqual(expected);
  // Trang Đơn hàng đọc lại đúng bộ lọc đó và gọi backend với nguyên chuỗi.
  await expect(page.getByTestId("orders")).toBeVisible();
  await expect.poll(() => orderCalls.at(-1)).toBe(`?${new URLSearchParams(expected)}`);

  // Back về nguyên bảng điều khiển, kể cả kỳ so sánh, và click tiếp được điểm khác.
  await page.goBack();
  await expect(page).toHaveURL(`/${DASHBOARD_QUERY}`);
  await expect(page.getByTestId("filter-comparison")).toHaveText("Kỳ liền trước");
  await pointAndClick(page, trendDot(page, 2), "late-rate-trend");

  await page.waitForURL(/\/orders\?/);
  // Nhóm cuối chỉ một ngày: /orders phải giữ khoảng đó chứ không bỏ đi.
  const singleDay = { ...expected, delivered_from: "2018-01-15", delivered_to: "2018-01-15" };
  expect(queryOf(page)).toEqual(singleDay);
  await expect.poll(() => orderCalls.at(-1)).toBe(`?${new URLSearchParams(singleDay)}`);
});

test("click cột bang mở đơn trễ của bang đó trong kỳ đang xem, kể cả kỳ mặc định", async ({
  page,
}) => {
  await mockBackend(page, DEFAULT_PERIOD_BODY);
  await page.goto(`/?seller_id=${SELLER_ID}`);

  await pointAndClick(page, stateBar(page, 1), "late-rate-by-state");

  await page.waitForURL(/\/orders\?/);
  expect(queryOf(page)).toEqual({
    delivery_outcome: "late",
    delivered_from: "2017-09-01",
    delivered_to: "2018-08-31",
    customer_state: "MA",
    seller_id: SELLER_ID,
  });
});

test("gợi ý bằng tiếng Anh", async ({ page, context }) => {
  await context.addCookies([
    { name: "NEXT_LOCALE", value: "en", url: "http://localhost:3000" },
  ]);
  await mockBackend(page, FILTERED_BODY);
  await page.goto(`/${DASHBOARD_QUERY}`);

  await trendDot(page, 1).hover();
  await expect(tooltipOf(page, "late-rate-trend")).toContainText("View late orders");
  await stateBar(page, 0).hover();
  await expect(tooltipOf(page, "late-rate-by-state")).toContainText("View late orders");
});
