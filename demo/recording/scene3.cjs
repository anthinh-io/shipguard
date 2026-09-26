// Cảnh 3: tạo đơn hẹn giao gấp (đơn B, rủi ro cao) rồi đơn hẹn giao rộng rãi (đơn A, rủi ro thấp) (4:30).
const { runScene, preLogin, ymd, writeState } = require("./lib.cjs");

// Điền biểu mẫu tạo đơn theo Bảng 4.1 của hướng dẫn; fast = điền nhanh, ít dừng (đơn thứ hai).
async function fillOrder(s, estDays, { fast = false, marks = {} } = {}) {
  const { page } = s;
  const d = fast ? 12 : 55;
  const item = page.getByTestId("create-order-item").first();
  await page.getByTestId("create-order-submit").waitFor();
  if (!fast) await s.moveTo("create-order-purchased-at");
  await s.fill("create-order-delivery-date", ymd(estDays));
  if (marks.address) await s.syncTo(marks.address);
  await s.pickOption("create-order-state", "SP");
  await s.type("create-order-city", "sao paulo", d);
  await s.type("create-order-zip", "01310", d);
  if (marks.item) await s.syncTo(marks.item);
  await s.click(item.getByTestId("filter-seller"));
  await s.type("filter-seller-input", "1f50f920", d);
  await page.getByTestId("seller-option").first().waitFor();
  await s.click(page.getByTestId("seller-option").first());
  await s.pickOption("create-order-category", "furniture_decor");
  await s.type("create-order-weight", "500", d);
  await s.type("create-order-price", "120.5", d);
  await s.type("create-order-freight", "25.3", d);
  if (marks.payment) await s.syncTo(marks.payment);
  await s.type("create-order-payment-amount", "145.8", d);
  await s.fill("create-order-payment-installments", "2");
  if (marks.submit) await s.syncTo(marks.submit);
  await s.click("create-order-submit");
  await page.waitForURL((u) => /^\/orders\/[0-9a-f]{32}$/.test(u.pathname));
  await page.getByTestId("risk-assessment-probability").waitFor();
  return page.url().split("/orders/")[1];
}

(async () => {
  const storageState = await preLogin("staff");
  await runScene("canh-3-tao-don", { storageState }, async (s) => {
    const { page } = s;
    await s.goto("/orders");
    await page.getByTestId("orders-table").waitFor();
    await s.syncTo(1);

    // Đơn B: hẹn giao sau 6 ngày.
    await s.click("orders-new");
    await s.syncTo(15);
    const orderB = await fillOrder(s, 6, { marks: { address: 35, item: 60, payment: 90, submit: 104 } });
    console.log("  đơn B", orderB, (await page.getByTestId("risk-assessment-probability").innerText()).replace(/\s+/g, " "));
    await s.syncTo(110);
    for (const id of ["risk-assessment-level", "risk-assessment-stage", "risk-assessment-seller", "risk-assessment-checkpoint"]) {
      if (await page.getByTestId(id).count()) {
        await s.moveTo(id, { steps: 20 });
        await s.syncTo(s.elapsed() + 4);
      }
    }
    await s.syncTo(150);

    await s.click("intervention-open");
    await s.pickOption("intervention-type", "Nhắc hoặc ưu tiên người bán");
    await s.type("intervention-note", "Đã nhắc người bán ưu tiên đóng gói đơn này.", 45);
    await s.syncTo(s.elapsed() + 1.5);
    await s.click("intervention-submit");
    await page.getByTestId("intervention-dialog").waitFor({ state: "hidden" });
    await page.getByTestId("risk-assessment-intervention-type").waitFor();
    await s.moveTo("risk-assessment-intervention-type");
    await s.syncTo(190);

    await s.click("milestone-record-submit");
    await page.getByTestId("risk-assessment-history-row").first().waitFor();
    await s.moveTo("risk-assessment-history-row");
    await s.syncTo(s.elapsed() + 6);
    await s.moveTo("risk-assessment-assessed-at");
    await s.syncTo(220);

    await s.type("order-notes-input", "Đã liên hệ người bán, hẹn bàn giao vận chuyển trong ngày mai.", 40);
    await s.click("order-notes-submit");
    await page.getByTestId("order-note").first().waitFor();
    await s.moveTo("order-note");
    await s.syncTo(235);

    // Đơn A: hẹn giao sau 25 ngày, điền nhanh.
    await s.click("nav-orders");
    await page.getByTestId("orders-table").waitFor();
    await s.click("orders-new");
    const orderA = await fillOrder(s, 25, { fast: true });
    console.log("  đơn A", orderA, (await page.getByTestId("risk-assessment-probability").innerText()).replace(/\s+/g, " "));
    writeState({ orderA, orderB });
    await s.moveTo("risk-assessment-probability");
    await s.syncTo(s.elapsed() + 4);
    await s.moveTo("risk-assessment-level");
    await s.syncTo(270);
  });
})();
