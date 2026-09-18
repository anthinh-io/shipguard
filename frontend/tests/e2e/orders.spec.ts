import { test, expect, type Page } from "@playwright/test";

import { mockSession } from "./session";

// Trình duyệt gọi thẳng backend (ADR-0002), nên mẫu chặn phải bám địa chỉ backend chứ
// không phải địa chỉ của trang.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const ORDERS_API = `${BACKEND_URL}/orders**`;
const FULL_ID = "e481f51cbdc54678b7cc49136f2d6af7";

// Múi giờ phía đông UTC: đọc "2018-10-17T02:30:18" như giờ máy sẽ lùi về 16/10 khi hiện
// theo UTC. Ghim múi giờ để bài test bắt được lỗi đó trên mọi máy chạy.
test.use({ timezoneId: "Asia/Ho_Chi_Minh" });

test.beforeEach(async ({ context }) => {
  await context.addCookies([
    { name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" },
  ]);
  await mockSession(context);
  // Thanh lọc tải danh sách bang khi mở trang. Không giả lập thì token giả tới backend
  // thật nhận 401, và apiFetch đưa cả trang về /login.
  await context.route(`${BACKEND_URL}/customer-states`, (route) =>
    route.fulfill({ json: ["RJ", "SP"] }),
  );
});

type Item = Record<string, string | number | null>;

function item(n: number, overrides: Item = {}): Item {
  return {
    order_id: `${n.toString(16).padStart(8, "0")}${"a".repeat(24)}`,
    order_status: "delivered",
    delivery_outcome: "on_time",
    purchased_at: "2018-10-17T02:30:18",
    estimated_delivery_date: "2018-10-30",
    delivered_at: "2018-10-25T10:00:00",
    customer_state: "SP",
    order_value: 100.5,
    risk_level: "not_assessed",
    ...overrides,
  };
}

function fullPage(page = 1): Item[] {
  return [
    item(0, { order_id: FULL_ID, order_value: 13664.08 }),
    ...Array.from({ length: 49 }, (_, i) => item(page * 100 + i + 1)),
  ];
}

// Trả trang đầy đủ 99.441 đơn, trừ khi có tìm mã: khi đó còn đúng một đơn.
async function mockOrders(page: Page, calls: string[] = []) {
  await page.route(ORDERS_API, (route) => {
    const url = new URL(route.request().url());
    calls.push(url.search);
    const orderId = url.searchParams.get("order_id");
    const pageNumber = Number(url.searchParams.get("page") ?? "1");
    return route.fulfill({
      json: orderId
        ? { items: [item(0, { order_id: FULL_ID })], total: 1, page: 1, page_size: 50 }
        : { items: fullPage(pageNumber), total: 99441, page: pageNumber, page_size: 50 },
    });
  });
  return calls;
}

test("mở từ sidebar thấy tổng số đơn và trang đầu 50 đơn đủ 9 cột", async ({ page }) => {
  await page.route(`${BACKEND_URL}/dashboard**`, (route) => route.fulfill({ status: 500 }));
  await mockOrders(page);

  await page.goto("/");
  await page.getByTestId("nav-orders").click();

  await expect(page).toHaveURL(/\/orders$/);
  await expect(page.getByRole("heading", { name: "Quản lý đơn hàng", exact: true })).toBeVisible();
  await expect(page.getByTestId("orders-total")).toContainText("99.441");
  await expect(page.getByTestId("order-row")).toHaveCount(50);

  const cells = page.getByTestId("order-row").first().getByRole("cell");
  await expect(cells).toHaveCount(9);
  await expect(cells.nth(0)).toHaveText("e481f51c");
  await expect(cells.nth(1)).toHaveText("Đã giao");
  await expect(cells.nth(2)).toHaveText("Đúng hạn");
  await expect(cells.nth(3)).toHaveText("Chưa đánh giá");
  await expect(cells.nth(4)).toHaveText("17/10/2018");
  await expect(cells.nth(5)).toHaveText("30/10/2018");
  await expect(cells.nth(6)).toHaveText("25/10/2018");
  await expect(cells.nth(7)).toHaveText("SP");
  await expect(cells.nth(8)).toHaveText("R$ 13.664,08");
});

test("gõ tiền tố mã đơn thì gọi lại đúng một lần và URL mang theo từ khoá", async ({
  page,
}) => {
  const calls = await mockOrders(page);

  await page.goto("/orders");
  await expect(page.getByTestId("order-row")).toHaveCount(50);
  expect(calls).toHaveLength(1);

  await page.getByTestId("orders-search").fill("E481F5");

  await expect.poll(() => calls.length).toBe(2);
  expect(calls[1]).toContain("order_id=E481F5");
  await expect(page).toHaveURL(/order_id=E481F5/);
  await expect(page.getByTestId("order-row")).toHaveCount(1);
});

test("URL đổi từ ngoài thì ô tìm đổi theo", async ({ page }) => {
  const calls = await mockOrders(page);

  await page.goto("/orders?order_id=e481f5");
  await expect(page.getByTestId("orders-search")).toHaveValue("e481f5");

  // Bấm lại mục sidebar là một lần đổi URL không đi qua ô tìm.
  await page.getByTestId("nav-orders").click();

  await expect(page).toHaveURL(/\/orders$/);
  await expect(page.getByTestId("orders-search")).toHaveValue("");
  await expect(page.getByTestId("order-row")).toHaveCount(50);
  // Ô tìm rỗng khớp URL rỗng, nên không có lần gọi nào đưa từ khoá cũ trở lại.
  await page.waitForTimeout(500);
  expect(calls.every((search) => search === "" || search === "?order_id=e481f5")).toBe(
    true,
  );
});

test("di chuột lên mã rút gọn thì hiện đủ mã đơn", async ({ page }) => {
  await mockOrders(page);

  await page.goto("/orders");
  await page.getByTestId("order-id").first().hover();

  await expect(page.getByRole("tooltip")).toContainText(FULL_ID);
});

test("bấm tiêu đề cột giá trị thì sắp giảm dần, bấm lần nữa thì đảo chiều", async ({
  page,
}) => {
  const calls = await mockOrders(page);

  await page.goto("/orders?page=4");
  await expect(page.getByTestId("order-row")).toHaveCount(50);

  await page.getByTestId("sort-order_value").click();
  await expect.poll(() => calls.length).toBe(2);
  // Đổi cách sắp thì về trang 1: trang 4 của một thứ tự khác là một tập đơn khác hẳn.
  expect(new URLSearchParams(calls[1]).toString()).toBe("sort=order_value");
  await expect(page).toHaveURL(/\/orders\?sort=order_value$/);
  await expect(page.getByTestId("header-order_value")).toHaveAttribute(
    "aria-sort",
    "descending",
  );

  await page.getByTestId("sort-order_value").click();
  await expect.poll(() => calls.length).toBe(3);
  expect(calls[2]).toContain("direction=asc");
  await expect(page.getByTestId("header-order_value")).toHaveAttribute(
    "aria-sort",
    "ascending",
  );
});

test("nhảy thẳng tới một trang bất kỳ, tổng số đơn không đổi", async ({ page }) => {
  const calls = await mockOrders(page);

  await page.goto("/orders");
  await expect(page.getByTestId("order-row")).toHaveCount(50);
  await expect(page.getByTestId("orders-page-count")).toContainText("1.989");

  await page.getByTestId("orders-page-input").fill("1000");
  await page.getByTestId("orders-page-input").press("Enter");

  await expect.poll(() => calls.length).toBe(2);
  expect(calls[1]).toBe("?page=1000");
  await expect(page).toHaveURL(/page=1000/);
  await expect(page.getByTestId("order-row")).toHaveCount(50);
  await expect(page.getByTestId("orders-total")).toContainText("99.441");
});

test("trang vượt quá tổng số trang thì kẹp về trang cuối", async ({ page }) => {
  const calls = await mockOrders(page);

  await page.goto("/orders");
  await expect(page.getByTestId("order-row")).toHaveCount(50);
  await page.getByTestId("orders-page-input").fill("999999");
  await page.getByTestId("orders-page-input").press("Enter");

  await expect.poll(() => calls.length).toBe(2);
  expect(calls[1]).toBe("?page=1989");
});

test("không đơn nào khớp mã thì báo rõ, không phải trang trắng hay lỗi", async ({
  page,
}) => {
  await page.route(ORDERS_API, (route) =>
    route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 50 } }),
  );

  await page.goto("/orders?order_id=zzz");

  await expect(page.getByTestId("orders-no-match")).toContainText("zzz");
  await expect(page.getByTestId("orders-error")).toHaveCount(0);
  await expect(page.getByTestId("order-row")).toHaveCount(0);
});

test("mở đường liên kết đồng nghiệp gửi thì thấy đúng từ khoá, thứ tự và trang", async ({
  page,
}) => {
  const calls = await mockOrders(page);

  await page.goto("/orders?order_id=abc&sort=delivered_at&direction=asc&page=3");

  await expect.poll(() => calls.length).toBe(1);
  expect(Object.fromEntries(new URLSearchParams(calls[0]))).toEqual({
    order_id: "abc",
    sort: "delivered_at",
    direction: "asc",
    page: "3",
  });
  await expect(page.getByTestId("orders-search")).toHaveValue("abc");
  await expect(page.getByTestId("header-delivered_at")).toHaveAttribute(
    "aria-sort",
    "ascending",
  );
});

test("máy chủ lỗi thì hiện thông báo lỗi, không lẫn với trạng thái không có đơn", async ({
  page,
}) => {
  await page.route(ORDERS_API, (route) => route.fulfill({ status: 500 }));

  await page.goto("/orders");

  await expect(page.getByTestId("orders-error")).toContainText("500");
  await expect(page.getByTestId("orders-no-match")).toHaveCount(0);
});

test("kết quả giao hiện đúng nhãn, ô trống hiện gạch ngang", async ({ page }) => {
  await page.route(ORDERS_API, (route) =>
    route.fulfill({
      json: {
        items: [
          item(1, { delivery_outcome: "late" }),
          item(2, {
            order_status: "canceled",
            delivery_outcome: "no_outcome",
            delivered_at: null,
            order_value: null,
          }),
        ],
        total: 2,
        page: 1,
        page_size: 50,
      },
    }),
  );

  await page.goto("/orders");

  const outcomes = page.getByTestId("delivery-outcome");
  await expect(outcomes).toHaveText(["Trễ", "Chưa có kết quả"]);
  const canceled = page.getByTestId("order-row").nth(1).getByRole("cell");
  await expect(canceled.nth(1)).toHaveText("Đã hủy");
  await expect(canceled.nth(6)).toHaveText("—");
  await expect(canceled.nth(8)).toHaveText("—");
});
