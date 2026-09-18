import { test, expect, type Locator, type Page } from "@playwright/test";

import { signInForReal } from "./session";

// Chạy thật: không mock bất kỳ endpoint nào (khác mọi spec khác trong thư mục này), nên
// cần backend đang chạy VÀ đã huấn luyện mô hình thật (uv run python -m
// app.scripts.train_risk_model) trước khi chạy tệp này — cùng điều kiện tiên quyết với
// smoke.spec.ts. Bài duy nhất của #37 đi hết một vòng đời đơn nhiều người bán để chứng
// minh ba nguồn (đánh giá, đối chiếu, trang chỉ số) khớp nhau trên dữ liệu thật.

// Hai người bán thật của bộ Olist, cùng mã với seller.spec.ts (chạy thật) và
// test_order_lifecycle_route.py (backend).
const SELLER_A = "6560211a19b47992c3666cc44a7e94c0";
const SELLER_B = "4a3ca9315b744ce9f8e9374361493884";

test.beforeEach(async ({ context }) => {
  await context.addCookies([
    { name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" },
  ]);
  await signInForReal(context);
});

async function pickOption(page: Page, trigger: Locator, name: string) {
  await trigger.click();
  await page.getByRole("option", { name, exact: true }).click();
}

async function pickFirstOption(page: Page, trigger: Locator) {
  await trigger.click();
  await page.getByRole("option").first().click();
}

// Cùng lý do với create-order.spec.ts: ô gõ và danh sách gợi ý được portal ra ngoài dòng
// sản phẩm, nên phải thao tác qua locator cấp trang sau khi bấm đúng nút của dòng.
async function pickSellerById(page: Page, row: Locator, sellerId: string) {
  await row.getByTestId("filter-seller").click();
  await page.getByTestId("filter-seller-input").fill(sellerId.slice(0, 8));
  await expect(page.getByTestId("seller-option").first()).toBeVisible();
  await page.getByTestId("seller-option").first().click();
}

async function reconciliationTotal(page: Page, checkpoint: string): Promise<number> {
  await page.goto("/model-metrics");
  const row = page.getByTestId("reconciliation-row").filter({ hasText: checkpoint });
  const text = await row.getByTestId("reconciliation-total").textContent();
  return Number(text);
}

test("vòng đời đơn nhiều người bán chạy thật: đánh giá, đối chiếu, và trang chỉ số cập nhật", async ({
  page,
}) => {
  const totalBefore = await reconciliationTotal(page, "Vừa đặt hàng");

  await page.goto("/orders/new");
  await pickOption(page, page.getByTestId("create-order-state"), "SP");
  await page.getByTestId("create-order-city").fill("sao paulo");
  await page.getByTestId("create-order-zip").fill("01310");

  const items = page.getByTestId("create-order-item");
  await pickSellerById(page, items.nth(0), SELLER_A);
  await pickFirstOption(page, items.nth(0).getByTestId("create-order-category"));
  await items.nth(0).getByTestId("create-order-price").fill("100");
  await items.nth(0).getByTestId("create-order-freight").fill("15");

  await page.getByTestId("create-order-add-item").click();
  await expect(items).toHaveCount(2);
  await pickSellerById(page, items.nth(1), SELLER_B);
  await pickFirstOption(page, items.nth(1).getByTestId("create-order-category"));
  await items.nth(1).getByTestId("create-order-price").fill("50");
  await items.nth(1).getByTestId("create-order-freight").fill("10");

  await page
    .getByTestId("create-order-payment")
    .first()
    .getByTestId("create-order-payment-amount")
    .fill("175");

  await page.getByTestId("create-order-submit").click();

  // Thấy lần đánh giá đầu tiên (order_placed) ngay khi trang chi tiết mở ra.
  await expect(page).toHaveURL(/\/orders\/[0-9a-f]{32}$/);
  const orderId = page.url().split("/").pop()!;
  await expect(page.getByTestId("risk-assessment-checkpoint")).toHaveText("Vừa đặt hàng");

  // Ghi nhận duyệt thanh toán rồi bàn giao — lịch sử có ba lần (một dòng nổi bật + hai
  // dòng lịch sử).
  await page.getByTestId("milestone-record-submit").click();
  await expect(page.getByTestId("risk-assessment-checkpoint")).toHaveText("Đã duyệt thanh toán");
  await expect(page.getByTestId("risk-assessment-history-row")).toHaveCount(1);

  await page.getByTestId("milestone-record-submit").click();
  await expect(page.getByTestId("risk-assessment-checkpoint")).toHaveText(
    "Đã bàn giao vận chuyển",
  );
  await expect(page.getByTestId("risk-assessment-history-row")).toHaveCount(2);

  // Ghi nhận đã giao — mỗi lần đánh giá hiện rõ đúng/sai, kể cả hai dòng lịch sử.
  await page.getByTestId("milestone-record-submit").click();
  await expect(page.getByTestId("risk-assessment-outcome")).toBeVisible();
  await expect(page.getByTestId("risk-assessment-history-outcome")).toHaveCount(2);

  // Tìm lại đơn trong danh sách.
  await page.goto(`/orders?order_id=${orderId.slice(0, 8)}`);
  await expect(page.getByTestId("orders-total")).toHaveText("1 đơn");

  // Số lần đối chiếu ở mốc đặt hàng trên trang chỉ số tăng lên — không khẳng định vào một
  // con số cụ thể, chỉ vào xu hướng tăng (dữ liệu tích lũy qua nhiều lần chạy).
  const totalAfter = await reconciliationTotal(page, "Vừa đặt hàng");
  expect(totalAfter).toBeGreaterThan(totalBefore);
});
