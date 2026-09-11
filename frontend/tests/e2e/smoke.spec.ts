import { test, expect } from "@playwright/test";

test("trang chủ hiển thị trạng thái kết nối backend qua HTTP thật", async ({ page }) => {
  await page.goto("/");

  const status = page.getByTestId("backend-status");
  await expect(status).toBeVisible();
  await expect(status).toContainText(/Backend: (ok|degraded)/);
});
