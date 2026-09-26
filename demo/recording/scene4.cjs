// Cảnh 4: hủy đơn A (đơn rủi ro thấp tạo ở Cảnh 3) (0:45).
const { runScene, preLogin, readState } = require("./lib.cjs");

(async () => {
  const { orderA } = readState();
  if (!orderA) throw new Error("Chưa có state.json: chạy Cảnh 3 trước.");
  const storageState = await preLogin("staff");
  await runScene("canh-4-huy-don", { storageState }, async (s) => {
    const { page } = s;
    await s.goto(`/orders/${orderA}`);
    await page.getByTestId("order-detail-id").waitFor();
    await s.moveTo("order-milestone-actions");
    await s.syncTo(4);
    await s.click("milestone-cancel-open");
    await page.getByTestId("cancel-order-dialog").waitFor();
    await s.syncTo(15);

    await s.click(page.getByRole("button", { name: "Giữ đơn" }));
    await page.getByTestId("cancel-order-dialog").waitFor({ state: "hidden" });
    await s.syncTo(s.elapsed() + 1.5);
    await s.click("milestone-cancel-open");
    await page.getByTestId("cancel-order-dialog").waitFor();
    await s.syncTo(s.elapsed() + 1.5);
    await s.click("cancel-order-confirm");
    await page.getByTestId("cancel-order-dialog").waitFor({ state: "hidden" });
    await page.getByTestId("milestone-actions-empty").waitFor();
    await s.moveTo("order-detail-status");
    await s.syncTo(45);
  });
})();
