import { test, expect, type Page } from "@playwright/test";

import { mockSession } from "./session";

// Trình duyệt gọi thẳng backend (ADR-0002), nên mẫu chặn phải bám địa chỉ backend chứ
// không phải địa chỉ của trang.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const DASHBOARD_API = `${BACKEND_URL}/dashboard**`;
const SELLERS_API = `${BACKEND_URL}/sellers**`;

const SELLER_ID = "6560211a19b47992c3666cc44a7e94c0";
// Bang người bán cố ý khác mọi bang khách trong mock: nút hiện "PR" thì chắc chắn nhãn
// lấy từ lần tra người bán, không lẫn với ô chọn bang.
const SELLER = {
  seller_id: SELLER_ID,
  seller_city: "curitiba",
  seller_state: "PR",
  delivered_orders: 42,
};

const SHARED_QUERY = `?start_date=2018-01-01&end_date=2018-01-30&customer_state=SP&seller_id=${SELLER_ID}&comparison=previous`;

test.beforeEach(async ({ context }) => {
  await context.addCookies([
    { name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" },
  ]);
  await mockSession(context);
});

// Nội dung số liệu không phải điều cần kiểm ở đây: lời gọi mang đúng chuỗi truy vấn của
// đường liên kết mới là "số liệu khớp bộ lọc". Ba khối so sánh để null như phản hồi thật
// khi không so sánh — mock không phải mô tả một phản hồi mà backend không tạo ra được.
const BODY = {
  reporting_period: { start_date: "2018-01-01", end_date: "2018-01-30" },
  filter_options: { customer_states: ["AL", "SP"] },
  kpis: {
    delivered_orders: 75548,
    late_orders: 2,
    on_time_rate: 0.9,
    payment_approval: { median_days: 0.01, p90_days: 1.44 },
    seller_handling: { median_days: 1.82, p90_days: 5.99 },
    carrier_transit: { median_days: 7.1, p90_days: 18.9 },
    late_related_low_review_rate: 0.32,
  },
  late_rate_trend: { granularity: "day", points: [] },
  late_rate_by_state: [
    { customer_state: "SP", delivered_orders: 75548, late_orders: 2, late_rate: 0.1 },
  ],
  small_sample: false,
  comparison_period: null,
  comparison_kpis: null,
  comparison_late_rate_trend: null,
};

async function mock(page: Page, sellers: unknown[] = [SELLER]): Promise<string[]> {
  const calls: string[] = [];
  await page.route(SELLERS_API, (route) => route.fulfill({ json: sellers }));
  await page.route(DASHBOARD_API, (route) => {
    calls.push(new URL(route.request().url()).search);
    return route.fulfill({ json: BODY });
  });
  return calls;
}

async function pick(page: Page, testId: string, option: string) {
  await page.getByTestId(testId).click();
  await page.getByRole("option", { name: option }).click();
}

test("đồng nghiệp mở đường liên kết được gửi thì thấy đúng bộ lọc và số liệu đó", async ({
  page,
}) => {
  const calls = await mock(page);

  await page.goto(`/${SHARED_QUERY}`);
  await expect(page.getByTestId("kpi-grid")).toBeVisible();

  // Đúng một lần gọi, mang nguyên chuỗi của đường liên kết.
  expect(calls).toEqual([SHARED_QUERY]);
  await expect(page.getByTestId("filter-date-range")).toContainText("2018");
  await expect(page.getByTestId("filter-customer-state")).toHaveText("SP");
  await expect(page.getByTestId("filter-seller")).toContainText("6560211a");
  await expect(page.getByTestId("filter-comparison")).toHaveText("Kỳ liền trước");
});

test("số liệu chưa về hoặc tải hỏng thì ô bang vẫn hiện bang trên đường liên kết", async ({
  page,
}) => {
  await page.route(SELLERS_API, (route) => route.fulfill({ json: [SELLER] }));
  // Danh sách bang đi kèm phản hồi /dashboard; hỏng lời gọi đó thì danh sách rỗng, và ô
  // chọn bang không được vì thế mà trống trong khi đường liên kết đang lọc theo SP.
  await page.route(DASHBOARD_API, (route) => route.fulfill({ status: 500, json: {} }));

  await page.goto(`/${SHARED_QUERY}`);

  await expect(page.getByTestId("dashboard-error")).toBeVisible();
  await expect(page.getByTestId("filter-customer-state")).toHaveText("SP");
});

test("tải lại trang thì mọi bộ lọc vẫn nguyên", async ({ page }) => {
  const calls = await mock(page);

  await page.goto("/");
  await pick(page, "filter-customer-state", "SP");
  await expect.poll(() => calls.length).toBe(2);
  await pick(page, "filter-comparison", "Kỳ liền trước");
  await expect.poll(() => calls.length).toBe(3);
  await expect(page).toHaveURL(/\/\?customer_state=SP&comparison=previous$/);

  await page.reload();

  await expect(page.getByTestId("kpi-grid")).toBeVisible();
  await expect.poll(() => calls.length).toBe(4);
  expect(calls[3]).toBe("?customer_state=SP&comparison=previous");
  await expect(page.getByTestId("filter-customer-state")).toHaveText("SP");
  await expect(page.getByTestId("filter-comparison")).toHaveText("Kỳ liền trước");
});

test("bấm Back thì trở về bộ lọc ngay trước đó", async ({ page }) => {
  const calls = await mock(page);

  await page.goto("/");
  await pick(page, "filter-customer-state", "SP");
  await expect.poll(() => calls.length).toBe(2);
  await pick(page, "filter-comparison", "Kỳ liền trước");
  await expect.poll(() => calls.length).toBe(3);

  await page.goBack();
  await expect.poll(() => calls.at(-1)).toBe("?customer_state=SP");
  await expect(page.getByTestId("filter-comparison")).toHaveText("Không so sánh");
  await expect(page.getByTestId("filter-customer-state")).toHaveText("SP");

  await page.goBack();
  await expect.poll(() => calls.at(-1)).toBe("");
  await expect(page.getByTestId("filter-customer-state")).toHaveText("Tất cả các bang");
});

test("đường liên kết có người bán thì ô người bán hiện đúng người bán đó", async ({
  page,
}) => {
  await mock(page);

  await page.goto(`/?seller_id=${SELLER_ID}`);

  const seller = page.getByTestId("filter-seller");
  await expect(seller).toContainText("6560211a");
  await expect(seller).toContainText("PR");
  await expect(seller).not.toContainText("Tất cả người bán");
});

test("tra người bán không ra thì ô vẫn hiện mã chứ không để trống", async ({ page }) => {
  await mock(page, []);

  await page.goto(`/?seller_id=${SELLER_ID}`);
  await expect(page.getByTestId("kpi-grid")).toBeVisible();

  await expect(page.getByTestId("filter-seller")).toContainText("6560211a");
  await expect(page.getByTestId("filter-seller")).not.toContainText("Tất cả người bán");
});

test("xoá hết bộ lọc thì đường liên kết không còn mang bộ lọc nào", async ({ page }) => {
  const calls = await mock(page);

  await page.goto(`/${SHARED_QUERY}`);
  await expect.poll(() => calls.length).toBe(1);

  await page.getByTestId("filter-clear-all").click();

  await expect.poll(() => calls.length).toBe(2);
  expect(calls[1]).toBe("");
  // Kiểm cả dấu "?": new URL("/?").search cũng là chuỗi rỗng.
  await expect(page).toHaveURL(/\/$/);
});

test("mở không kèm bộ lọc thì vẫn là kỳ mặc định và không ghi gì lên đường liên kết", async ({
  page,
}) => {
  const calls = await mock(page);

  await page.goto("/");
  await expect(page.getByTestId("kpi-grid")).toBeVisible();

  expect(calls).toEqual([""]);
  await expect(page).toHaveURL(/\/$/);
});
