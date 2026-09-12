import { test, expect, type Page } from "@playwright/test";

// Trình duyệt gọi thẳng backend (ADR-0002), nên mẫu chặn phải bám địa chỉ backend chứ
// không phải địa chỉ của trang.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const DASHBOARD_API = `${BACKEND_URL}/dashboard**`;

// Ghim ngôn ngữ ở tiếng Việt cho cả bộ smoke. Các bài dưới đây khẳng định vào chuỗi đã
// hiển thị, nên để chúng bám vào ngôn ngữ mặc định là gài sẵn một lần hỏng vào ngày ai
// đó đổi mặc định.
test.beforeEach(async ({ context }) => {
  await context.addCookies([
    { name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" },
  ]);
});

// Không khẳng định vào giá trị KPI cụ thể: dữ liệu nạp lại được và kỳ mặc định tính
// động, nên con số đổi mà hành vi vẫn đúng. Bộ số vàng khẳng định ở tầng tính toán.
async function expectKpiTiles(page: Page) {
  await expect(page.getByTestId("filter-bar")).toBeVisible();
  await expect(page.getByTestId("kpi-on-time-rate")).toBeVisible();
  await expect(page.getByTestId("kpi-late-orders")).toBeVisible();
  await expect(page.getByTestId("kpi-payment-approval")).toBeVisible();
  await expect(page.getByTestId("kpi-seller-handling")).toBeVisible();
  await expect(page.getByTestId("kpi-carrier-transit")).toBeVisible();
  await expect(page.getByTestId("kpi-late-related-low-review-rate")).toBeVisible();
  await expect(page.getByTestId("reporting-period")).toContainText("Kỳ báo cáo:");
  await expect(page.getByTestId("late-rate-trend")).toBeVisible();
  await expect(page.getByTestId("late-rate-by-state")).toBeVisible();
}

test("mở bảng điều khiển là thấy ngay số liệu, không cần chọn bộ lọc", async ({
  page,
}) => {
  await page.goto("/");

  await expectKpiTiles(page);
  await expect(page.getByTestId("dashboard-error")).toHaveCount(0);
});

test("mỗi lần mở trang chỉ sinh đúng một lần gọi máy chủ", async ({ page }) => {
  let calls = 0;
  await page.route(DASHBOARD_API, async (route) => {
    calls += 1;
    await route.continue();
  });

  await page.goto("/");
  await expectKpiTiles(page);

  expect(calls).toBe(1);
});

test("máy chủ không phản hồi thì hiện thông báo lỗi rõ ràng", async ({ page }) => {
  await page.route(DASHBOARD_API, (route) => route.abort());

  await page.goto("/");

  await expect(page.getByTestId("dashboard-error")).toBeVisible();
  await expect(page.getByTestId("kpi-grid")).toHaveCount(0);
  // Thanh bộ lọc không được biến mất đúng lúc người dùng cần nó nhất — sau một lần
  // lọc hỏng, vẫn phải còn đường để đổi bộ lọc và thử lại.
  await expect(page.getByTestId("filter-bar")).toBeVisible();
});

test("số liệu chưa về thì hiện trạng thái đang tải", async ({ page }) => {
  // Giữ phản hồi lại một nhịp để trạng thái tải quan sát được một cách tất định, thay
  // vì chớp qua trong vài mili giây.
  await page.route(DASHBOARD_API, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    await route.continue();
  });

  await page.goto("/");

  await expect(page.getByTestId("dashboard-loading")).toBeVisible();
  await expectKpiTiles(page);
  await expect(page.getByTestId("dashboard-loading")).toHaveCount(0);
});
