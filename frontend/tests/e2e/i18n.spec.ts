import { test, expect, type Page } from "@playwright/test";

// Trình duyệt gọi thẳng backend (ADR-0002), nên mẫu chặn phải bám địa chỉ backend chứ
// không phải địa chỉ của trang.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const DASHBOARD_API = `${BACKEND_URL}/dashboard**`;

// Dữ liệu thật nạp lại được nên con số đổi mà hành vi vẫn đúng, không khẳng định vào
// được. Bộ số cố định dưới đây mở ra một việc khác: kiểm quy ước định dạng của từng
// ngôn ngữ, thứ chỉ nhìn thấy khi biết trước giá trị đầu vào.
const PINNED = {
  reporting_period: { start_date: "2017-09-01", end_date: "2018-08-31" },
  kpis: { delivered_orders: 12345, late_orders: 678, on_time_rate: 0.9323 },
};

async function pinDashboard(page: Page) {
  const calls = { count: 0 };
  await page.route(DASHBOARD_API, (route) => {
    calls.count += 1;
    return route.fulfill({ json: PINNED });
  });
  return calls;
}

test("đổi ngôn ngữ thì mọi nhãn trên bảng điều khiển đổi theo", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByTestId("kpi-on-time-rate")).toContainText(
    "Tỷ lệ giao đúng hạn",
  );
  await expect(page.getByTestId("kpi-late-orders")).toContainText("Đơn giao trễ");
  await expect(page.getByTestId("reporting-period")).toContainText("Kỳ báo cáo:");

  await page.getByTestId("language-toggle").click();

  await expect(page.getByTestId("kpi-on-time-rate")).toContainText("On-time rate");
  await expect(page.getByTestId("kpi-late-orders")).toContainText("Late orders");
  await expect(page.getByTestId("reporting-period")).toContainText("Reporting period:");
});

test("tải lại trang vẫn giữ ngôn ngữ đã chọn", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("language-toggle").click();
  await expect(page.getByTestId("kpi-late-orders")).toContainText("Late orders");

  await page.reload();

  // Bấm rồi mới tải lại, không gieo sẵn cookie: gieo sẵn chỉ chứng minh được đường
  // đọc, còn tiêu chí này nói về đường ghi.
  await expect(page.getByTestId("kpi-late-orders")).toContainText("Late orders");
});

test("mặc định là tiếng Việt khi chưa chọn gì", async ({ page }) => {
  // Playwright cấp context mới cho mỗi bài nên cookie rỗng sẵn, đúng bằng trạng thái
  // của người lần đầu mở trang. Gieo cookie ở đây là làm hỏng chính điều đang kiểm.
  await page.goto("/");

  await expect(page.getByTestId("kpi-late-orders")).toContainText("Đơn giao trễ");
});

test("đổi ngôn ngữ không thêm tiền tố nào vào đường dẫn", async ({ page }) => {
  await page.goto("/");

  await page.getByTestId("language-toggle").click();
  await expect(page.getByTestId("kpi-late-orders")).toContainText("Late orders");

  expect(new URL(page.url()).pathname).toBe("/");
});

test("số và ngày hiển thị đúng quy ước của từng ngôn ngữ", async ({ page }) => {
  const calls = await pinDashboard(page);
  await page.goto("/");

  // Tiếng Việt: dấu phẩy thập phân, dấu chấm phân nhóm, ngày dd/mm/yyyy. Neo phần
  // trăm bằng regex vì vi-VN chèn U+00A0 trước dấu %.
  await expect(page.getByTestId("kpi-on-time-rate")).toContainText(/93,23\s*%/);
  await expect(page.getByTestId("kpi-on-time-rate")).toContainText("12.345");
  await expect(page.getByTestId("kpi-late-orders")).toContainText("678");
  await expect(page.getByTestId("reporting-period")).toContainText(
    "01/09/2017 – 31/08/2018",
  );

  await page.getByTestId("language-toggle").click();

  // Tiếng Anh: dấu chấm thập phân, dấu phẩy phân nhóm, và thứ tự tháng/ngày/năm.
  await expect(page.getByTestId("kpi-on-time-rate")).toContainText(/93\.23\s*%/);
  await expect(page.getByTestId("kpi-on-time-rate")).toContainText("12,345");
  await expect(page.getByTestId("reporting-period")).toContainText(
    "09/01/2017 – 08/31/2018",
  );

  // Đổi ngôn ngữ chỉ vẽ lại chứ không gắn lại cây component, nên dữ liệu đã tải vẫn
  // nằm nguyên trong client. Đếm ở đây vì bộ số cố định làm hai nhánh trông y hệt nhau:
  // gắn lại rồi gọi lại máy chủ cũng cho ra đúng những chuỗi vừa khẳng định ở trên.
  expect(calls.count).toBe(1);
});
