// Cảnh 6: Super Admin quản trị tài khoản, rồi so sánh thanh bên và quyền giữa ba vai trò (2:30).
const { runScene } = require("./lib.cjs");

const AN_EMAIL = "an.nguyen@congty.com";

runScene("canh-6-quan-tri", {}, async (s) => {
  const { page } = s;
  const anRow = () => page.getByTestId("user-row").filter({ has: page.getByRole("cell", { name: AN_EMAIL, exact: true }) });
  const openMenu = async () => {
    await page.getByRole("menu").waitFor({ state: "hidden" }).catch(() => {});
    await s.click(anRow().getByTestId("user-actions"));
  };

  await s.goto("/login");
  await s.syncTo(1);
  await s.login("admin");
  await page.getByTestId("kpi-on-time-rate").waitFor();
  await s.click("nav-admin");
  await page.getByTestId("user-admin-table").waitFor();
  await s.syncTo(15);

  await s.click("user-admin-create");
  const dialog = page.getByTestId("create-user-dialog");
  await dialog.waitFor();
  await s.type("create-user-name", "Nguyễn Văn An");
  await s.type("create-user-email", AN_EMAIL);
  await s.pickOption("create-user-role", "Nhân viên vận hành");
  await s.type("create-user-password", "ShipGuard@2026", 40);
  await s.click("create-user-submit");
  await dialog.waitFor({ state: "hidden" });
  await anRow().waitFor();
  await s.moveTo(anRow());
  await s.syncTo(45);

  await openMenu();
  await s.click("user-action-role");
  await page.getByRole("menuitemradio").first().waitFor();
  await s.syncTo(s.elapsed() + 3);
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await openMenu();
  await s.click("user-action-lock");
  await page.getByTestId("lock-user-dialog").waitFor();
  await s.syncTo(s.elapsed() + 2);
  await s.click("lock-user-confirm");
  await page.getByTestId("lock-user-dialog").waitFor({ state: "hidden" });
  await anRow().getByText("Đã khóa").waitFor();
  await s.moveTo(anRow());
  await s.syncTo(70);

  await openMenu();
  await s.click("user-action-unlock");
  await anRow().getByText("Đang hoạt động").waitFor();
  await s.syncTo(s.elapsed() + 2);
  await openMenu();
  await s.click("user-action-reset-password");
  await page.getByTestId("reset-user-password-dialog").waitFor();
  await s.type("reset-user-password-new", "MatKhauMoi@2026", 40);
  await s.type("reset-user-password-confirm", "MatKhauMoi@2026", 40);
  await s.syncTo(s.elapsed() + 2);
  await s.click(page.getByRole("button", { name: "Hủy" }));
  await page.getByTestId("reset-user-password-dialog").waitFor({ state: "hidden" });
  await s.syncTo(95);

  await s.logout();
  await s.login("manager");
  await page.getByTestId("kpi-on-time-rate").waitFor();
  await s.click("nav-admin");
  await page.getByTestId("user-admin-table").waitFor();
  await s.moveTo("user-admin-table");
  await s.syncTo(s.elapsed() + 4);
  await s.click("user-admin-create");
  await page.getByTestId("create-user-dialog").waitFor();
  await s.click("create-user-role");
  await page.getByRole("option").first().waitFor();
  await s.syncTo(s.elapsed() + 4);
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await page.getByTestId("create-user-dialog").waitFor({ state: "hidden" });
  await s.syncTo(120);

  await s.logout();
  await s.login("staff");
  await page.getByTestId("kpi-on-time-rate").waitFor();
  await s.moveTo("nav-orders");
  await s.syncTo(s.elapsed() + 4);
  await s.goto("/admin/users");
  await page.getByTestId("user-admin-forbidden").waitFor();
  await s.moveTo("user-admin-forbidden");
  await s.syncTo(150);
});
