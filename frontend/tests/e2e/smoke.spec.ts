import { test, expect, type Page } from "@playwright/test";

import { signInForReal } from "./session";

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
  await signInForReal(context);
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

test("bảng điều khiển nói rõ giao đúng ngày cam kết là đúng hạn", async ({
  page,
}) => {
  // Quy ước này quyết định con số trên ô tỷ lệ đúng hạn, nhưng nó nằm trong cột sinh
  // is_late — người đọc không có cách nào biết nếu màn hình không nói ra.
  await page.goto("/");

  await expect(page.getByTestId("on-time-definition")).toBeVisible();
  await expect(page.getByTestId("on-time-definition")).toContainText(
    "đúng ngày đã cam kết",
  );
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

// Khác ô KPI ở trên, các con số này không đổi theo kỳ mặc định: tổng số đơn, đơn giá trị
// lớn nhất và mã "e481f5" là bất biến của bộ CSV — chính là bộ số vàng của #19.
test("trang Đơn hàng chạy thật: tổng số đơn, tìm theo mã và sắp theo giá trị", async ({
  page,
}) => {
  await page.goto("/orders");

  await expect(page.getByTestId("orders-total")).toHaveText("99.441 đơn");
  await expect(page.getByTestId("order-row")).toHaveCount(50);

  await page.getByTestId("orders-search").fill("E481F5");
  await expect(page.getByTestId("orders-total")).toHaveText("1 đơn");
  await expect(page.getByTestId("order-row")).toHaveCount(1);

  await page.goto("/orders?sort=order_value");
  await expect(
    page.getByTestId("order-row").first().getByRole("cell").last(),
  ).toHaveText("R$ 13.664,08");
});

// Bộ số vàng của #20, cũng là bất biến của bộ CSV. 6.534 chứ không phải 6.535 (tính cả đơn
// đã hủy có ngày giao) hay 7.826 (so theo giờ thay vì theo ngày).
test("thanh lọc đơn hàng chạy thật: trạng thái, kết quả giao và trọn khoảng ngày đặt", async ({
  page,
}) => {
  await page.goto("/orders?order_status=shipped");
  await expect(page.getByTestId("orders-total")).toHaveText("1.107 đơn");

  await page.goto("/orders?delivery_outcome=late");
  await expect(page.getByTestId("orders-total")).toHaveText("6.534 đơn");

  await page.goto("/orders?purchased_from=2016-09-04&purchased_to=2018-10-17");
  await expect(page.getByTestId("orders-total")).toHaveText("99.441 đơn");

  await page.getByTestId("filter-clear-all").click();
  await expect(page).toHaveURL(/\/orders$/);
  await expect(page.getByTestId("orders-total")).toHaveText("99.441 đơn");
});
