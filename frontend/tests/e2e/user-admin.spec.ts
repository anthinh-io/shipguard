import { test, expect, type BrowserContext, type Page } from "@playwright/test";

import { mockSession, switchLanguage } from "./session";

// Trình duyệt gọi thẳng backend (ADR-0006), nên mẫu chặn phải bám địa chỉ backend chứ
// không phải địa chỉ của trang.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

// Luôn giả lập /users: tài khoản không xóa được, chạy với backend thật là để lại tài khoản
// rác sau mỗi lần chạy. Luồng thật (đăng nhập lại, thu hồi phiên, quy tắc bảo vệ) nằm ở
// backend/tests/test_user_admin_routes.py.
const USERS_API = new RegExp(`^${BACKEND_URL}/users(/\\d+(/password)?)?$`);

type User = {
  id: number;
  email: string;
  display_name: string;
  role: "operations_staff" | "logistics_manager" | "super_admin";
  is_locked: boolean;
};

const MANAGER = {
  id: 2,
  email: "khoa@shipguard.vn",
  display_name: "Trần Khoa",
  role: "logistics_manager",
} as const;

function seedUsers(): User[] {
  return [
    {
      id: 1,
      email: "admin@shipguard.vn",
      display_name: "Super Admin",
      role: "super_admin",
      is_locked: false,
    },
    { ...MANAGER, is_locked: false },
    {
      id: 3,
      email: "lan@shipguard.vn",
      display_name: "Nguyễn Lan",
      role: "operations_staff",
      is_locked: false,
    },
    {
      id: 4,
      email: "minh@shipguard.vn",
      display_name: "Lê Minh",
      role: "logistics_manager",
      is_locked: true,
    },
  ];
}

type Call = { method: string; path: string; body: unknown };

// Máy chủ giả giữ danh sách trong bộ nhớ để phản hồi của PATCH khớp dữ liệu bảng sau đó.
async function mockUsersApi(page: Page, options: { createStatus?: number } = {}) {
  const users = seedUsers();
  const calls: Call[] = [];
  await page.route(USERS_API, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const body = request.postDataJSON();
    calls.push({ method, path, body });
    const id = Number(path.split("/")[2]);
    if (method === "GET") {
      return route.fulfill({ json: users });
    }
    if (method === "POST" && path === "/users") {
      if (options.createStatus) {
        return route.fulfill({
          status: options.createStatus,
          json: { detail: "Email is already in use" },
        });
      }
      const created = { id: 5, is_locked: false, ...body, password: undefined };
      users.push(created);
      return route.fulfill({ status: 201, json: created });
    }
    if (method === "PATCH") {
      const user = users.find((candidate) => candidate.id === id)!;
      Object.assign(user, body);
      return route.fulfill({ json: user });
    }
    return route.fulfill({ status: 204 });
  });
  return calls;
}

async function signInAsManager(context: BrowserContext) {
  await mockSession(context, MANAGER);
}

// Khớp nguyên ô email: lọc theo chữ thì "khoa@" cũng chứa "hoa@".
function row(page: Page, email: string) {
  return page
    .getByTestId("user-row")
    .filter({ has: page.getByRole("cell", { name: email, exact: true }) });
}

// Chờ menu của lần trước đóng hẳn: trong nhịp hiệu ứng đóng, hai menu cùng nằm trong DOM.
async function openActions(page: Page, email: string) {
  await expect(page.getByRole("menu")).toHaveCount(0);
  await row(page, email).getByTestId("user-actions").click();
}

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" }]);
});

test("nhân viên vận hành không thấy mục Quản trị, gõ thẳng đường dẫn thì bị từ chối", async ({
  page,
  context,
}) => {
  await mockSession(context);
  await page.route(USERS_API, (route) =>
    route.fulfill({ status: 403, json: { detail: "Not allowed to manage users" } }),
  );

  await page.goto("/admin/users");

  await expect(page.getByTestId("user-admin-forbidden")).toHaveText(
    "Bạn không có quyền truy cập trang quản trị.",
  );
  await expect(page.getByTestId("user-name")).toHaveText("Nguyễn Lan");
  await expect(page.getByTestId("nav-dashboard")).toBeVisible();
  await expect(page.getByTestId("nav-admin")).toHaveCount(0);
  await expect(page.getByTestId("user-admin-table")).toHaveCount(0);
});

test("quản lý hậu cần mở mục Quản trị thì thấy mọi tài khoản với tên, email, vai trò, trạng thái", async ({
  page,
  context,
}) => {
  await signInAsManager(context);
  await mockUsersApi(page);

  // Mở thẳng trang chứ không đi từ bảng điều khiển: trang đó sẽ gọi /dashboard thật bằng
  // token giả, nhận 401 và bị đưa về /login giữa chừng.
  await page.goto("/admin/users");

  await expect(page.getByTestId("nav-admin")).toHaveAttribute("data-active", "true");
  await expect(page.getByRole("heading", { name: "Quản trị" })).toBeVisible();
  await expect(page.getByTestId("user-row")).toHaveCount(4);
  const lan = row(page, "lan@shipguard.vn");
  await expect(lan).toContainText("Nguyễn Lan");
  await expect(lan.getByTestId("user-row-role")).toHaveText("Nhân viên vận hành");
  await expect(lan.getByTestId("user-row-status")).toHaveText("Đang hoạt động");
  await expect(row(page, "minh@shipguard.vn").getByTestId("user-row-status")).toHaveText("Đã khóa");
});

test("dòng Super Admin và dòng của chính mình không có menu thao tác", async ({
  page,
  context,
}) => {
  await signInAsManager(context);
  await mockUsersApi(page);

  await page.goto("/admin/users");

  await expect(page.getByTestId("user-row")).toHaveCount(4);
  await expect(row(page, "admin@shipguard.vn").getByTestId("user-actions")).toHaveCount(0);
  await expect(row(page, "khoa@shipguard.vn").getByTestId("user-actions")).toHaveCount(0);
  await expect(row(page, "khoa@shipguard.vn")).toContainText("(bạn)");
  await expect(row(page, "lan@shipguard.vn").getByTestId("user-actions")).toBeVisible();
});

test("tạo tài khoản: ô vai trò chỉ có hai lựa chọn, lưu xong thì người mới hiện trong bảng", async ({
  page,
  context,
}) => {
  await signInAsManager(context);
  const calls = await mockUsersApi(page);
  await page.goto("/admin/users");

  await page.getByTestId("user-admin-create").click();
  const dialog = page.getByTestId("create-user-dialog");
  await dialog.getByTestId("create-user-name").fill("Phạm Hoa");
  await dialog.getByTestId("create-user-email").fill("hoa@shipguard.vn");
  await dialog.getByTestId("create-user-role").click();
  await expect(page.getByRole("option")).toHaveText(["Nhân viên vận hành", "Quản lý hậu cần"]);
  await page.getByRole("option", { name: "Quản lý hậu cần" }).click();
  await dialog.getByTestId("create-user-password").fill("staple-battery-horse");
  await dialog.getByTestId("create-user-submit").click();

  await expect(dialog).toHaveCount(0);
  await expect(row(page, "hoa@shipguard.vn").getByTestId("user-row-role")).toHaveText(
    "Quản lý hậu cần",
  );
  expect(calls.filter((call) => call.method === "POST")).toEqual([
    {
      method: "POST",
      path: "/users",
      body: {
        display_name: "Phạm Hoa",
        email: "hoa@shipguard.vn",
        role: "logistics_manager",
        password: "staple-battery-horse",
      },
    },
  ]);
});

test("tạo tài khoản bằng email đã có thì báo email đã được dùng và giữ hộp thoại", async ({
  page,
  context,
}) => {
  await signInAsManager(context);
  await mockUsersApi(page, { createStatus: 409 });
  await page.goto("/admin/users");

  await page.getByTestId("user-admin-create").click();
  const dialog = page.getByTestId("create-user-dialog");
  await dialog.getByTestId("create-user-name").fill("Nguyễn Lan");
  await dialog.getByTestId("create-user-email").fill("LAN@shipguard.vn");
  await dialog.getByTestId("create-user-password").fill("staple-battery-horse");
  await dialog.getByTestId("create-user-submit").click();

  await expect(dialog.getByTestId("create-user-error")).toHaveText(
    "Email này đã được dùng cho một tài khoản khác.",
  );
  await expect(dialog).toBeVisible();
  await expect(page.getByTestId("user-row")).toHaveCount(4);
});

test("khóa tài khoản phải qua bước xác nhận; hủy thì không gửi gì", async ({ page, context }) => {
  await signInAsManager(context);
  const calls = await mockUsersApi(page);
  await page.goto("/admin/users");
  const patches = () => calls.filter((call) => call.method === "PATCH");

  await openActions(page, "lan@shipguard.vn");
  await page.getByTestId("user-action-lock").click();
  const dialog = page.getByTestId("lock-user-dialog");
  await expect(dialog).toContainText("Nguyễn Lan");
  await dialog.getByRole("button", { name: "Hủy" }).click();
  await expect(dialog).toHaveCount(0);
  expect(patches()).toEqual([]);

  await openActions(page, "lan@shipguard.vn");
  await page.getByTestId("user-action-lock").click();
  await page.getByTestId("lock-user-confirm").click();

  await expect(row(page, "lan@shipguard.vn").getByTestId("user-row-status")).toHaveText("Đã khóa");
  expect(patches()).toEqual([{ method: "PATCH", path: "/users/3", body: { is_locked: true } }]);
});

test("mở khóa và đổi vai trò gửi thẳng, bảng cập nhật theo phản hồi", async ({ page, context }) => {
  await signInAsManager(context);
  const calls = await mockUsersApi(page);
  await page.goto("/admin/users");

  await openActions(page, "minh@shipguard.vn");
  await expect(page.getByTestId("user-action-lock")).toHaveCount(0);
  await page.getByTestId("user-action-unlock").click();
  await expect(row(page, "minh@shipguard.vn").getByTestId("user-row-status")).toHaveText(
    "Đang hoạt động",
  );

  await openActions(page, "lan@shipguard.vn");
  await page.getByTestId("user-action-role").click();
  await page.getByRole("menuitemradio", { name: "Quản lý hậu cần" }).click();
  await expect(row(page, "lan@shipguard.vn").getByTestId("user-row-role")).toHaveText(
    "Quản lý hậu cần",
  );

  expect(calls.filter((call) => call.method === "PATCH")).toEqual([
    { method: "PATCH", path: "/users/4", body: { is_locked: false } },
    { method: "PATCH", path: "/users/3", body: { role: "logistics_manager" } },
  ]);
});

test("đặt lại mật khẩu cho người quên thì gửi mật khẩu mới và báo đã đặt lại", async ({
  page,
  context,
}) => {
  await signInAsManager(context);
  const calls = await mockUsersApi(page);
  await page.goto("/admin/users");

  await openActions(page, "lan@shipguard.vn");
  await page.getByTestId("user-action-reset-password").click();
  const dialog = page.getByTestId("reset-user-password-dialog");
  await dialog.getByTestId("reset-user-password-new").fill("staple-battery-horse");
  await dialog.getByTestId("reset-user-password-confirm").fill("staple-battery-horse");
  await dialog.getByTestId("reset-user-password-submit").click();

  await expect(dialog.getByTestId("reset-user-password-success")).toHaveText(
    "Đã đặt lại mật khẩu cho Nguyễn Lan.",
  );
  expect(calls.filter((call) => call.method === "POST")).toEqual([
    {
      method: "POST",
      path: "/users/3/password",
      body: { new_password: "staple-battery-horse" },
    },
  ]);
});

test("trang quản trị song ngữ", async ({ page, context }) => {
  await signInAsManager(context);
  await mockUsersApi(page);
  await page.goto("/admin/users");
  await expect(page.getByTestId("user-row")).toHaveCount(4);

  await switchLanguage(page);

  await expect(page.getByRole("heading", { name: "Administration" })).toBeVisible();
  const table = page.getByTestId("user-admin-table");
  await expect(table.getByRole("columnheader")).toContainText(["Name", "Email", "Role", "Status"]);
  await expect(row(page, "minh@shipguard.vn").getByTestId("user-row-status")).toHaveText("Locked");
  await expect(row(page, "khoa@shipguard.vn")).toContainText("(you)");

  await page.getByTestId("user-admin-create").click();
  const dialog = page.getByTestId("create-user-dialog");
  await expect(dialog.getByRole("heading", { name: "Create account" })).toBeVisible();
  await expect(dialog).toContainText("Initial password (at least 8 characters)");
  await dialog.getByRole("button", { name: "Cancel" }).click();

  await openActions(page, "lan@shipguard.vn");
  await expect(page.getByTestId("user-action-lock")).toHaveText("Lock account");
  await expect(page.getByTestId("user-action-reset-password")).toHaveText("Reset password");
});
