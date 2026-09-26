// Cảnh 2: Nhân viên vận hành đầu ngày, bảng điều khiển và tra cứu đơn (2:15).
const { runScene } = require("./lib.cjs");

runScene("canh-2-bang-dieu-khien", {}, async (s) => {
  const { page } = s;
  await s.goto("/login");
  await s.syncTo(1);
  await s.login("staff");
  await page.getByTestId("kpi-on-time-rate").waitFor();
  await s.syncTo(20);

  for (const id of ["kpi-on-time-rate", "kpi-late-orders", "kpi-payment-approval", "kpi-seller-handling", "kpi-carrier-transit"]) {
    await s.moveTo(id, { steps: 20 });
    await s.syncTo(s.elapsed() + 1.8);
  }
  await s.moveTo("kpi-on-time-rate", { steps: 20 });
  await s.syncTo(50);

  await page.evaluate(() => window.scrollTo(0, 0));
  await s.pickOption("filter-comparison", "Kỳ liền trước");
  await page.getByTestId("late-rate-trend").scrollIntoViewIfNeeded();
  await s.moveTo("late-rate-trend");
  await s.syncTo(70);

  await s.moveTo("late-rate-by-state");
  const bar = page.getByTestId("late-rate-by-state").locator(".recharts-bar-rectangle").nth(2);
  await bar.hover();
  await page.getByTestId("late-rate-by-state").locator(".recharts-tooltip-wrapper").getByText("Xem đơn trễ").waitFor();
  await s.syncTo(s.elapsed() + 1.5);
  await page.mouse.down();
  await page.mouse.up();
  await page.waitForURL((u) => u.pathname.startsWith("/orders"));
  await page.getByTestId("orders-table").waitFor();
  await s.syncTo(90);

  await s.click("filter-clear-all");
  await page.getByTestId("order-row").first().waitFor();
  await s.syncTo(s.elapsed() + 1.5);
  await s.moveTo("orders-total");
  await s.scrollBy(300, 1500);
  await s.syncTo(110);

  const olist = page.getByTestId("order-row").filter({ hasText: "Chưa đánh giá" }).filter({ hasText: "Đã giao" }).first();
  const shortId = (await olist.getByTestId("order-id").innerText()).trim().slice(0, 6);
  await s.type("orders-search", shortId, 90);
  await page.getByTestId("order-row").first().waitFor();
  await s.syncTo(s.elapsed() + 1);
  await s.click(page.getByTestId("order-row").first());
  await page.getByTestId("order-detail-id").waitFor();
  await s.moveTo("order-timeline");
  await s.syncTo(s.elapsed() + 4);
  await s.scrollBy(500, 2500);
  await s.syncTo(130);

  await page.goBack();
  await page.getByTestId("orders-table").waitFor();
  await s.click("orders-export");
  await s.syncTo(135);
});
