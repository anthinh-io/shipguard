import { test, expect, type Page } from "@playwright/test";

import { mockSession } from "./session";

// Trình duyệt gọi thẳng backend (ADR-0002), nên mẫu chặn phải bám địa chỉ backend chứ
// không phải địa chỉ của trang.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const ORDERS_API = `${BACKEND_URL}/orders**`;
const SELLERS_API = `${BACKEND_URL}/sellers**`;
const SELLER_ID = "6560211a19b47992c3666cc44a7e94c0";

const FILTER_PARAMS = [
  "order_status",
  "delivery_outcome",
  "purchased_from",
  "purchased_to",
  "delivered_from",
  "delivered_to",
  "customer_state",
  "seller_id",
];

test.beforeEach(async ({ context }) => {
  await context.addCookies([
    { name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" },
  ]);
  await mockSession(context);
  await context.route(`${BACKEND_URL}/customer-states`, (route) =>
    route.fulfill({ json: ["RJ", "SP"] }),
  );
  await context.route(SELLERS_API, (route) =>
    route.fulfill({
      json: [
        {
          seller_id: SELLER_ID,
          seller_city: "ibitinga",
          seller_state: "SP",
          delivered_orders: 1819,
        },
      ],
    }),
  );
});

function item(n: number) {
  return {
    order_id: `${n.toString(16).padStart(8, "0")}${"b".repeat(24)}`,
    order_status: "shipped",
    delivery_outcome: "no_outcome",
    purchased_at: "2018-01-17T02:30:18",
    estimated_delivery_date: "2018-01-30",
    delivered_at: null,
    customer_state: "SP",
    order_value: 100.5,
  };
}

// Tổng số đơn giả lập giảm dần theo số bộ lọc đang áp, để màn hình đổi được theo từng
// lần lọc mà bài test vẫn biết trước con số.
function totalFor(url: URL): number {
  const active = FILTER_PARAMS.filter((name) => url.searchParams.has(name));
  if (url.searchParams.get("order_status") === "shipped" && active.length === 1) {
    return 1107;
  }
  if (url.searchParams.get("delivery_outcome") === "late" && active.length === 1) {
    return 6534;
  }
  return active.length === 0 ? 99441 : 100 - active.length;
}

async function mockOrders(page: Page): Promise<URL[]> {
  const calls: URL[] = [];
  await page.route(ORDERS_API, (route) => {
    const url = new URL(route.request().url());
    calls.push(url);
    const total = totalFor(url);
    return route.fulfill({
      json: {
        items: Array.from({ length: Math.min(total, 50) }, (_, i) => item(i + 1)),
        total,
        page: Number(url.searchParams.get("page") ?? "1"),
        page_size: 50,
      },
    });
  });
  return calls;
}

async function pickOption(page: Page, testId: string, name: string) {
  await page.getByTestId(testId).click();
  await page.getByRole("option", { name, exact: true }).click();
}

// Cùng cách chọn ngày của trend.spec.ts: data-day là ngày theo giờ địa phương.
function dayCell(page: Page, day: Date) {
  return page.locator(`[data-slot="calendar"] [data-day="${day.toLocaleDateString()}"]`);
}

function isoDay(day: Date): string {
  const month = String(day.getMonth() + 1).padStart(2, "0");
  return `${day.getFullYear()}-${month}-${String(day.getDate()).padStart(2, "0")}`;
}

test("lọc trạng thái đang vận chuyển thì danh sách báo 1.107 đơn và URL mang bộ lọc", async ({
  page,
}) => {
  const calls = await mockOrders(page);
  await page.goto("/orders?page=4");
  await expect(page.getByTestId("orders-total")).toContainText("99.441");

  await pickOption(page, "filter-order-status", "Đang vận chuyển");

  await expect(page.getByTestId("orders-total")).toHaveText("1.107 đơn");
  // Đổi bộ lọc thì về trang 1: trang 4 của một tập đơn khác không có nghĩa gì.
  await expect(page).toHaveURL(/\/orders\?order_status=shipped$/);
  expect(calls.at(-1)?.searchParams.get("order_status")).toBe("shipped");
  expect(calls.at(-1)?.searchParams.has("page")).toBe(false);
});

test("lọc kết quả giao trễ thì danh sách báo 6.534 đơn", async ({ page }) => {
  await mockOrders(page);
  await page.goto("/orders");

  await pickOption(page, "filter-delivery-outcome", "Trễ");

  await expect(page.getByTestId("orders-total")).toHaveText("6.534 đơn");
  await expect(page).toHaveURL(/delivery_outcome=late/);
});

test("mới chọn ngày bắt đầu thì chưa lọc, chọn đủ hai đầu mới lọc", async ({ page }) => {
  const calls = await mockOrders(page);
  await page.goto("/orders");
  await expect(page.getByTestId("orders-total")).toContainText("99.441");

  const today = new Date();
  const start = new Date(today.getFullYear(), today.getMonth(), 10);
  const end = new Date(today.getFullYear(), today.getMonth(), 20);

  await page.getByTestId("filter-purchased-range").click();
  await dayCell(page, start).click();
  // Lịch vẫn mở chờ ngày thứ hai, và không có lời gọi nào mang nửa khoảng.
  await expect(page.locator('[data-slot="calendar"]')).toBeVisible();
  expect(calls.some((url) => url.searchParams.has("purchased_from"))).toBe(false);

  await dayCell(page, end).click();

  await expect.poll(() => calls.at(-1)?.searchParams.get("purchased_from")).toBe(isoDay(start));
  expect(calls.at(-1)?.searchParams.get("purchased_to")).toBe(isoDay(end));
  expect(calls.at(-1)?.searchParams.has("delivered_from")).toBe(false);
});

test.describe("ở múi giờ phía tây UTC", () => {
  test.use({ timezoneId: "America/Sao_Paulo" });

  test("mở lại lịch rồi chọn tiếp thì ngày đầu của khoảng đang áp không lùi một ngày", async ({
    page,
  }) => {
    const calls = await mockOrders(page);
    await page.goto("/orders?purchased_from=2018-01-05&purchased_to=2018-01-10");
    await expect(page.getByTestId("filter-purchased-range")).toContainText(
      "05/01/2018 – 10/01/2018",
    );

    // Khoảng đang áp là một khoảng đủ hai đầu; bấm một ngày sau nó thì react-day-picker
    // giữ ngày đầu và thay ngày cuối. Ngày đầu phải vẫn là 05/01, không phải 04/01.
    const today = new Date();
    await page.getByTestId("filter-purchased-range").click();
    await dayCell(page, new Date(today.getFullYear(), today.getMonth(), 15)).click();

    await expect.poll(() => calls.at(-1)?.searchParams.get("purchased_to")).not.toBe("2018-01-10");
    expect(calls.at(-1)?.searchParams.get("purchased_from")).toBe("2018-01-05");
  });
});

test("khoảng ngày giao là bộ lọc riêng, độc lập với khoảng ngày đặt", async ({ page }) => {
  const calls = await mockOrders(page);
  await page.goto("/orders?purchased_from=2017-01-01&purchased_to=2018-06-30");

  const today = new Date();
  await page.getByTestId("filter-delivered-range").click();
  await dayCell(page, new Date(today.getFullYear(), today.getMonth(), 3)).click();
  await dayCell(page, new Date(today.getFullYear(), today.getMonth(), 5)).click();

  await expect.poll(() => calls.at(-1)?.searchParams.has("delivered_from")).toBe(true);
  expect(calls.at(-1)?.searchParams.get("purchased_from")).toBe("2017-01-01");
  await expect(page.getByTestId("filter-purchased-range")).toContainText("01/01/2017");
});

test("kết hợp người bán, bang, kết quả giao và khoảng ngày đặt trong một lần gọi mỗi bước", async ({
  page,
}) => {
  const calls = await mockOrders(page);
  await page.goto("/orders?purchased_from=2017-01-01&purchased_to=2018-06-30");

  await page.getByTestId("filter-seller").click();
  const suggestionRequest = page.waitForRequest((request) =>
    request.url().startsWith(`${BACKEND_URL}/sellers?q=656`),
  );
  await page.getByTestId("filter-seller-input").fill("656");
  // Danh sách đơn gồm cả đơn chưa giao, nên gợi ý cả người bán chưa giao xong đơn nào,
  // và số trên gợi ý nói rõ là số đơn đã giao.
  expect(new URL((await suggestionRequest).url()).searchParams.get("delivered_only")).toBe(
    "false",
  );
  await expect(page.getByTestId("seller-option").first()).toContainText("1.819 đơn đã giao");
  await page.getByTestId("seller-option").first().click();
  await expect(page.getByTestId("filter-seller")).toContainText("6560211a… · SP");

  await pickOption(page, "filter-customer-state", "SP");
  await expect(page.getByTestId("orders-total")).toHaveText("96 đơn");
  await pickOption(page, "filter-delivery-outcome", "Trễ");

  // Tổng số đơn cập nhật theo lần lọc cuối.
  await expect(page.getByTestId("orders-total")).toHaveText("95 đơn");
  const last = calls.at(-1)!;
  expect(last.searchParams.get("seller_id")).toBe(SELLER_ID);
  expect(last.searchParams.get("customer_state")).toBe("SP");
  expect(last.searchParams.get("delivery_outcome")).toBe("late");
  expect(last.searchParams.get("purchased_from")).toBe("2017-01-01");
  expect(last.searchParams.get("purchased_to")).toBe("2018-06-30");
});

test("xoá hết bộ lọc thì quay về toàn bộ 99.441 đơn, giữ nguyên thứ tự sắp xếp", async ({
  page,
}) => {
  const calls = await mockOrders(page);
  await page.goto(
    `/orders?order_status=shipped&delivery_outcome=no_outcome&customer_state=SP&seller_id=${SELLER_ID}&sort=order_value&page=2`,
  );
  await expect(page.getByTestId("orders-total")).toHaveText("96 đơn");

  await page.getByTestId("filter-clear-all").click();

  await expect(page.getByTestId("orders-total")).toHaveText("99.441 đơn");
  await expect(page).toHaveURL(/\/orders\?sort=order_value$/);
  expect(FILTER_PARAMS.some((name) => calls.at(-1)!.searchParams.has(name))).toBe(false);
});

test("mở đường liên kết đủ bộ lọc hay tải lại trang thì mọi bộ lọc vẫn nguyên", async ({
  page,
}) => {
  const calls = await mockOrders(page);
  const link =
    "/orders?order_status=shipped&delivery_outcome=no_outcome" +
    "&purchased_from=2017-01-01&purchased_to=2018-06-30" +
    "&delivered_from=2018-01-01&delivered_to=2018-01-31" +
    `&customer_state=SP&seller_id=${SELLER_ID}`;

  for (const open of [() => page.goto(link), () => page.reload()]) {
    await open();

    await expect(page.getByTestId("filter-order-status")).toContainText("Đang vận chuyển");
    await expect(page.getByTestId("filter-delivery-outcome")).toContainText("Chưa có kết quả");
    await expect(page.getByTestId("filter-purchased-range")).toContainText(
      "01/01/2017 – 30/06/2018",
    );
    await expect(page.getByTestId("filter-delivered-range")).toContainText(
      "01/01/2018 – 31/01/2018",
    );
    await expect(page.getByTestId("filter-customer-state")).toContainText("SP");
    await expect(page.getByTestId("filter-seller")).toContainText("6560211a…");
    await expect(page.getByTestId("orders-total")).toHaveText("92 đơn");
    for (const name of FILTER_PARAMS) {
      expect(calls.at(-1)!.searchParams.has(name)).toBe(true);
    }
  }
});

test("đường liên kết chỉ có một đầu khoảng ngày thì danh sách chưa lọc theo khoảng đó", async ({
  page,
}) => {
  const calls = await mockOrders(page);
  await page.goto("/orders?purchased_from=2018-01-01");

  await expect(page.getByTestId("orders-total")).toHaveText("99.441 đơn");
  expect(calls.at(-1)!.searchParams.has("purchased_from")).toBe(false);
  await expect(page.getByTestId("filter-purchased-range")).toHaveText("Ngày đặt");
});

test("bộ lọc không khớp đơn nào thì nói về bộ lọc, không nói về mã đơn", async ({ page }) => {
  await page.route(ORDERS_API, (route) =>
    route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 50 } }),
  );

  await page.goto("/orders?order_id=e481f5&customer_state=RR");

  await expect(page.getByTestId("orders-no-match")).toHaveText(
    "Không có đơn nào khớp các bộ lọc đang chọn.",
  );
});
