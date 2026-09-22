import path from "node:path";

import { test, expect, type Page } from "@playwright/test";

import { signInForReal } from "./session";

// Chụp ảnh giao diện thật cho Chương 3 báo cáo thu hoạch (docs/report/) — không phải bài
// kiểm thử hồi quy, không assert hành vi, chỉ điều hướng + chụp. Xem
// C:\Users\ThinhNguyen\.claude\plans\ti-p-t-c-l-p-k-logical-shore.md để biết mục con nào
// dùng ảnh nào.
const OUT_DIR = path.join(__dirname, "..", "..", "..", "docs", "report", "images", "screenshots");

// Đơn Olist lịch sử đã có sẵn 3 lần đánh giá rủi ro cao (order_placed/payment_approved/
// handed_to_carrier), chưa ghi nhận biện pháp can thiệp, đã giao xong — dùng để chụp tổng
// quan đơn hàng đầy đủ (dòng thời gian 4 mốc, thông tin sản phẩm/người bán/địa chỉ/thanh
// toán/đánh giá thật từ CSV Olist) và khối "Ghi nhận biện pháp can thiệp".
const HIGH_RISK_ORDER_ID = "5ce509f57e3e210d9b65141d806cc7f6";

test.use({ viewport: { width: 1440, height: 900 } });

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" }]);
});

async function shot(page: Page, name: string, opts?: { fullPage?: boolean }) {
  await page.screenshot({
    path: path.join(OUT_DIR, `${name}.png`),
    fullPage: opts?.fullPage ?? false,
  });
}

test("3.1.1 Đăng nhập", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByTestId("login-form")).toBeVisible();
  await shot(page, "3.1.1-dang-nhap");

  await page.getByTestId("login-email").fill("khong-ton-tai@shipguard.local");
  await page.getByTestId("login-password").fill("mat-khau-sai");
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("login-error")).toBeVisible();
  await shot(page, "3.1.1-dang-nhap-loi");
});

test("3.1.2 Dashboard hiệu suất", async ({ page, context }) => {
  await signInForReal(context);
  await page.goto("/");
  await expect(page.getByTestId("kpi-on-time-rate")).toBeVisible();
  await expect(page.getByTestId("late-rate-trend")).toBeVisible();
  await expect(page.getByTestId("late-rate-by-state")).toBeVisible();
  await shot(page, "3.1.2-dashboard", { fullPage: true });
});

test("3.1.3 Danh sách đơn hàng", async ({ page, context }) => {
  await signInForReal(context);
  await page.goto("/orders");
  await expect(page.getByTestId("orders-table")).toBeVisible();
  await shot(page, "3.1.3-danh-sach-don-hang");
});

test("3.1.4 Tạo đơn hàng mới + 3.1.5 Chi tiết đơn hàng (đơn mới tạo)", async ({
  page,
  context,
}) => {
  await signInForReal(context);
  await page.goto("/orders/new");
  await expect(page.getByTestId("create-order-submit")).toBeVisible();

  await page.getByTestId("create-order-city").fill("sao paulo");
  await page.getByTestId("create-order-zip").fill("01310");
  await page.getByTestId("create-order-state").click();
  await page.getByRole("option").first().click();

  await page.getByTestId("filter-seller").click();
  await page.getByTestId("filter-seller-input").fill("3f0e48d2");
  await page.getByTestId("seller-option").first().click();

  await page.getByTestId("create-order-category").click();
  await page.getByRole("option").first().click();

  await page.getByTestId("create-order-weight").fill("500");
  await page.getByTestId("create-order-price").fill("189.90");
  await page.getByTestId("create-order-freight").fill("21.50");

  await page.getByTestId("create-order-payment-amount").fill("211.40");

  // Chụp trước khi gửi — đây là ảnh cho 3.1.4, biểu mẫu đã điền đủ nhưng chưa submit.
  await shot(page, "3.1.4-tao-don-hang-moi", { fullPage: true });

  await page.getByTestId("create-order-submit").click();
  await page.waitForURL((url) => /\/orders\/[^/]+$/.test(url.pathname) && !url.pathname.endsWith("/new"));
  const newOrderId = page.url().split("/orders/")[1];

  // --- 3.1.5 Chi tiết đơn hàng, dùng đơn vừa tạo (order_placed, chưa mốc nào khác) ---
  await expect(page.getByTestId("order-detail-id")).toHaveText(newOrderId);

  // Hình 3.1.5.3 — ghi nhận mốc vòng đời tiếp theo (đơn còn mở, có đủ nút thao tác).
  await expect(page.getByTestId("order-milestone-actions")).toBeVisible();
  await page.getByTestId("order-milestone-actions").screenshot({
    path: path.join(OUT_DIR, "3.1.5.3-ghi-nhan-moc-vong-doi.png"),
  });

  // Hình 3.1.5.4 — hộp thoại xác nhận huỷ đơn.
  await page.getByTestId("milestone-cancel-open").click();
  await expect(page.getByTestId("cancel-order-dialog")).toBeVisible();
  await page.getByTestId("cancel-order-dialog").screenshot({
    path: path.join(OUT_DIR, "3.1.5.4-huy-don-hang.png"),
  });
  await page.getByRole("button", { name: "Giữ đơn" }).click();
  await expect(page.getByTestId("cancel-order-dialog")).toBeHidden();

  // Hình 3.1.5.5 — thêm ghi chú nội bộ thật cho đơn.
  await page.getByTestId("order-notes-input").fill(
    "Đã liên hệ người bán để xác nhận thời gian xử lý đơn.",
  );
  await page.getByTestId("order-notes-submit").click();
  await expect(page.getByTestId("order-note")).toHaveCount(1);
  await page.getByTestId("order-notes").screenshot({
    path: path.join(OUT_DIR, "3.1.5.5-ghi-chu-noi-bo.png"),
  });
});

test("3.1.5 Chi tiết đơn hàng (đơn rủi ro cao, đã giao) — tổng quan + can thiệp", async ({
  page,
  context,
}) => {
  await signInForReal(context);
  await page.goto(`/orders/${HIGH_RISK_ORDER_ID}`);
  await expect(page.getByTestId("order-detail-id")).toHaveText(HIGH_RISK_ORDER_ID);

  // Hình 3.1.5.1 — tổng quan: trạng thái/giá trị đơn + dòng thời gian đủ 4 mốc + thông tin
  // sản phẩm/người bán/địa chỉ/thanh toán/đánh giá thật (đơn Olist gốc).
  await shot(page, "3.1.5.1-tong-quan-don-hang", { fullPage: true });

  // Hình 3.1.5.2 — đánh giá rủi ro + mở hộp thoại ghi nhận biện pháp can thiệp (đơn này
  // còn "cần xử lý": High Risk, chưa can thiệp, chưa bị đơn khác thay thế).
  await expect(page.getByTestId("intervention-open")).toBeVisible();
  await page.getByTestId("intervention-open").click();
  await expect(page.getByTestId("intervention-dialog")).toBeVisible();
  await page.getByTestId("intervention-type").click();
  await page.getByRole("option").first().click();
  await page
    .getByTestId("intervention-note")
    .fill("Đã nhắc người bán đóng gói và bàn giao cho đơn vị vận chuyển sớm hơn.");
  await page.getByTestId("intervention-dialog").screenshot({
    path: path.join(OUT_DIR, "3.1.5.2-ghi-nhan-can-thiep.png"),
  });
});

test("3.2.1 Quản lý tài khoản người dùng", async ({ page, context }) => {
  await signInForReal(context);
  await page.goto("/admin/users");
  await expect(page.getByTestId("user-admin-table")).toBeVisible();

  // Hình 3.2.1.1 — danh sách tài khoản (Super Admin + 2 tài khoản seed sẵn).
  await shot(page, "3.2.1.1-danh-sach-tai-khoan");

  // Hình 3.2.1.2 — tạo tài khoản mới (dữ liệu thật, tài khoản test riêng, không đụng vào
  // 3 tài khoản seed sẵn).
  await page.getByTestId("user-admin-create").click();
  await expect(page.getByTestId("create-user-dialog")).toBeVisible();
  await page.getByTestId("create-user-name").fill("Tài khoản chụp ảnh báo cáo");
  await page.getByTestId("create-user-email").fill("report-screenshot-user@shipguard.vn");
  await page.getByTestId("create-user-password").fill("ReportScreenshot123!");
  await page.getByTestId("create-user-dialog").screenshot({
    path: path.join(OUT_DIR, "3.2.1.2-tao-tai-khoan.png"),
  });
  await page.getByTestId("create-user-submit").click();
  await expect(page.getByTestId("create-user-dialog")).toBeHidden();

  // Hình 3.2.1.3 — menu hành động + đổi vai trò, trên tài khoản Operations Staff seed sẵn
  // (không đổi thật — chỉ mở submenu rồi đóng lại, không bấm chọn vai trò nào).
  const staffRow = page
    .getByTestId("user-row")
    .filter({ hasText: "operations_staff@shipguard.vn" });
  await staffRow.getByTestId("user-actions").click();
  await page.getByTestId("user-action-role").click();
  await expect(page.getByRole("menuitemradio").first()).toBeVisible();
  await page.screenshot({ path: path.join(OUT_DIR, "3.2.1.3-menu-hanh-dong.png") });
  await page.mouse.click(10, 10);
  await expect(page.getByTestId("user-action-role")).toBeHidden();

  // Hình 3.2.1.4 — xác nhận khoá tài khoản (mở rồi Hủy, không khoá thật tài khoản seed).
  await staffRow.getByTestId("user-actions").click();
  await expect(page.getByTestId("user-action-lock")).toBeVisible();
  await page.getByTestId("user-action-lock").click();
  await expect(page.getByTestId("lock-user-dialog")).toBeVisible();
  await page.getByTestId("lock-user-dialog").screenshot({
    path: path.join(OUT_DIR, "3.2.1.4-xac-nhan-khoa.png"),
  });
  await page.getByRole("button", { name: "Hủy" }).click();
  await expect(page.getByTestId("lock-user-dialog")).toBeHidden();

  // Hình 3.2.1.5 — đặt lại mật khẩu (điền form rồi Hủy, không đổi mật khẩu thật của tài
  // khoản seed).
  await staffRow.getByTestId("user-actions").click();
  await expect(page.getByTestId("user-action-reset-password")).toBeVisible();
  await page.getByTestId("user-action-reset-password").click();
  await expect(page.getByTestId("reset-user-password-dialog")).toBeVisible();
  await page.getByTestId("reset-user-password-new").fill("KhongDoiThat123!");
  await page.getByTestId("reset-user-password-confirm").fill("KhongDoiThat123!");
  await page.getByTestId("reset-user-password-dialog").screenshot({
    path: path.join(OUT_DIR, "3.2.1.5-dat-lai-mat-khau.png"),
  });
  await page.getByRole("button", { name: "Hủy" }).click();
});

test("3.2.2 Chỉ số độ tin cậy mô hình", async ({ page, context }) => {
  await signInForReal(context);
  await page.goto("/model-metrics");
  await expect(page.getByTestId("model-metrics-overview")).toBeVisible();
  await shot(page, "3.2.2-chi-so-mo-hinh", { fullPage: true });
});
