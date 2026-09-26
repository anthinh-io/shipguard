// Cảnh 5: Quản lý hậu cần xem Chỉ số mô hình (2:00).
const { runScene } = require("./lib.cjs");

runScene("canh-5-chi-so-mo-hinh", {}, async (s) => {
  const { page } = s;
  await s.goto("/login");
  await s.syncTo(1);
  await s.login("manager");
  await page.getByTestId("kpi-on-time-rate").waitFor();
  await s.click("nav-modelMetrics");
  await page.getByTestId("model-metrics-overview").waitFor();
  await s.syncTo(15);

  for (const id of ["model-metrics-model-version", "model-metrics-selected-algorithm", "model-metrics-threshold"]) {
    await s.moveTo(id, { steps: 20 });
    await s.syncTo(s.elapsed() + 3);
  }
  await s.syncTo(30);

  await s.moveTo("model-metrics-f1-status");
  await s.syncTo(60);

  await s.moveTo("model-metrics-algorithm-table");
  await s.scrollBy(200, 800);
  await s.syncTo(80);

  await s.moveTo("reconciliation-table");
  await page.getByTestId("reconciliation-row").first().waitFor();
  await s.syncTo(s.elapsed() + 6);
  await s.moveTo("reconciliation-small-sample");
  await s.syncTo(120);
});
