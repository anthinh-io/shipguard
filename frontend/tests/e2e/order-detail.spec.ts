import { test, expect, type Page } from "@playwright/test";

import { mockSession } from "./session";

// Trình duyệt gọi thẳng backend (ADR-0002), nên mẫu chặn phải bám địa chỉ backend chứ
// không phải địa chỉ của trang.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
// `**` vượt cả dấu gạch chéo, nên một mẫu này bắt cả /orders lẫn /orders/{id}. Một handler
// rẽ nhánh theo đường dẫn, để danh sách không bị trả nhầm cho trang chi tiết.
const ORDERS_API = `${BACKEND_URL}/orders**`;

const LATE_ID = "e481f51cbdc54678b7cc49136f2d6af7";
const BARE_ID = "b0000000000000000000000000000000";
const SELLER_A = "3504c0cb71d7fa48d967e0e4c94d59d9";
const SELLER_B = "289cdb325fb7e7f891c38608bf9e0962";

// Múi giờ phía đông UTC: đọc dấu thời gian như giờ máy sẽ lệch giờ và có khi lệch ngày.
test.use({ timezoneId: "Asia/Ho_Chi_Minh" });

test.beforeEach(async ({ context }) => {
  await context.addCookies([
    { name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" },
  ]);
  await mockSession(context);
  await context.route(`${BACKEND_URL}/customer-states`, (route) =>
    route.fulfill({ json: ["RJ", "SP"] }),
  );
});

const LATE_ORDER = {
  order_id: LATE_ID,
  order_status: "delivered",
  delivery_outcome: "late",
  order_value: 146.88,
  timeline: {
    purchased_at: "2017-10-02T10:56:33",
    payment_approved_at: "2017-10-02T11:07:15",
    handed_to_carrier_at: "2017-10-04T19:55:00",
    delivered_at: "2017-10-20T21:25:13",
    estimated_delivery_date: "2017-10-18",
    payment_approval_days: 0.0074,
    seller_handling_days: 2.3589,
    carrier_transit_days: 16.0612,
  },
  address: {
    customer_city: "sao paulo",
    customer_state: "SP",
    customer_zip_code_prefix: "03149",
  },
  items: [
    {
      order_item_id: 1,
      product_id: "87285b34884572647811a353c7ac498a",
      category: "housewares",
      price: 29.99,
      freight_value: 8.72,
      seller_id: SELLER_A,
    },
    {
      order_item_id: 2,
      product_id: "595fac2a385ac33a80bd5114aec74eb8",
      category: null,
      price: 99.9,
      freight_value: 8.27,
      seller_id: SELLER_B,
    },
  ],
  sellers: [
    { seller_id: SELLER_B, seller_city: "ibitinga", seller_state: "SP" },
    { seller_id: SELLER_A, seller_city: "maua", seller_state: "SP" },
  ],
  payments: [
    { payment_sequential: 1, payment_type: "credit_card", payment_installments: 3, payment_value: 100 },
    { payment_sequential: 2, payment_type: "voucher", payment_installments: 1, payment_value: 46.88 },
  ],
  reviews: [
    {
      review_score: 2,
      comment_title: null,
      comment_message: "Chegou atrasado.",
      created_at: "2017-10-21T00:00:00",
    },
  ],
};

// Đơn mới tạo: chưa duyệt, chưa giao, không sản phẩm, không thanh toán, không đánh giá.
const BARE_ORDER = {
  order_id: BARE_ID,
  order_status: "created",
  delivery_outcome: "no_outcome",
  order_value: null,
  timeline: {
    purchased_at: "2018-02-09T17:21:04",
    payment_approved_at: null,
    handed_to_carrier_at: null,
    delivered_at: null,
    estimated_delivery_date: "2018-03-07",
    payment_approval_days: null,
    seller_handling_days: null,
    carrier_transit_days: null,
  },
  address: { customer_city: "rio de janeiro", customer_state: "RJ", customer_zip_code_prefix: "20231" },
  items: [],
  sellers: [],
  payments: [],
  reviews: [],
};

function listItem(orderId: string) {
  return {
    order_id: orderId,
    order_status: "delivered",
    delivery_outcome: "late",
    purchased_at: "2017-10-02T10:56:33",
    estimated_delivery_date: "2017-10-18",
    delivered_at: "2017-10-20T21:25:13",
    customer_state: "SP",
    order_value: 146.88,
  };
}

async function mockOrders(page: Page): Promise<URL[]> {
  const listCalls: URL[] = [];
  await page.route(ORDERS_API, (route) => {
    const url = new URL(route.request().url());
    // Ghi chú nội bộ có spec riêng (order-notes.spec.ts); ở đây chỉ cần cột ghi chú không báo lỗi.
    if (/^\/orders\/[^/]+\/notes$/.test(url.pathname)) {
      return route.fulfill({ json: [] });
    }
    const detailId = url.pathname.match(/^\/orders\/([^/]+)$/)?.[1];
    if (detailId !== undefined) {
      const body = { [LATE_ID]: LATE_ORDER, [BARE_ID]: BARE_ORDER }[decodeURIComponent(detailId)];
      return body
        ? route.fulfill({ json: body })
        : route.fulfill({ status: 404, json: { detail: "Order not found" } });
    }
    listCalls.push(url);
    return route.fulfill({
      json: {
        items: [listItem(LATE_ID), listItem(BARE_ID)],
        total: 99441,
        page: Number(url.searchParams.get("page") ?? "1"),
        page_size: 50,
      },
    });
  });
  return listCalls;
}

test("bấm một đơn trong danh sách thì mở trang riêng, đường liên kết mở lại được đúng đơn", async ({
  page,
}) => {
  await mockOrders(page);
  await page.goto("/orders");

  await page.getByTestId("order-row").first().getByRole("cell").nth(1).click();

  await expect(page).toHaveURL(new RegExp(`/orders/${LATE_ID}$`));
  await expect(page.getByTestId("order-detail-id")).toHaveText(LATE_ID);
  await expect(page.getByTestId("order-detail-status")).toHaveText("Đã giao");
  await expect(page.getByTestId("order-detail-outcome")).toHaveText("Trễ");

  await page.reload();
  await expect(page.getByTestId("order-detail-id")).toHaveText(LATE_ID);
});

test("đơn giao trễ: đủ bốn mốc, ngày cam kết cạnh ngày giao, và thời gian ba chặng", async ({
  page,
}) => {
  await mockOrders(page);
  await page.goto(`/orders/${LATE_ID}`);

  await expect(page.getByTestId("timeline-purchased-at")).toHaveText("10:56 02/10/2017");
  await expect(page.getByTestId("timeline-payment-approved-at")).toHaveText("11:07 02/10/2017");
  await expect(page.getByTestId("timeline-handed-to-carrier-at")).toHaveText("19:55 04/10/2017");
  await expect(page.getByTestId("timeline-delivered-at")).toHaveText("21:25 20/10/2017");
  await expect(page.getByTestId("timeline-estimated-delivery-date")).toHaveText("18/10/2017");
  await expect(page.getByTestId("stage-payment-approval")).toHaveText("0,01 ngày");
  await expect(page.getByTestId("stage-seller-handling")).toHaveText("2,36 ngày");
  await expect(page.getByTestId("stage-carrier-transit")).toHaveText("16,06 ngày");
  await expect(page.getByTestId("order-detail-value")).toContainText("R$ 146,88");
});

test("đơn hai người bán: từng sản phẩm có danh mục, giá, phí vận chuyển và người bán", async ({
  page,
}) => {
  await mockOrders(page);
  await page.goto(`/orders/${LATE_ID}`);

  const items = page.getByTestId("order-item");
  await expect(items).toHaveCount(2);
  await expect(items.nth(0)).toContainText("housewares");
  await expect(items.nth(0)).toContainText("R$ 29,99");
  await expect(items.nth(0)).toContainText("R$ 8,72");
  await expect(items.nth(0)).toContainText(SELLER_A);
  // Sản phẩm không có danh mục vẫn hiện, ghi rõ là chưa có.
  await expect(items.nth(1)).toContainText("Chưa có");
  await expect(items.nth(1)).toContainText(SELLER_B);

  await expect(page.getByTestId("order-seller")).toHaveCount(2);
  await expect(page.getByTestId("order-seller").first()).toContainText("ibitinga · SP");
});

test("thanh toán, địa chỉ giao và đánh giá của khách", async ({ page }) => {
  await mockOrders(page);
  await page.goto(`/orders/${LATE_ID}`);

  const payments = page.getByTestId("order-payment");
  await expect(payments).toHaveCount(2);
  await expect(payments.nth(0)).toContainText("Thẻ tín dụng");
  await expect(payments.nth(0)).toContainText("3");
  await expect(payments.nth(0)).toContainText("R$ 100,00");
  await expect(payments.nth(1)).toContainText("Phiếu mua hàng");

  const address = page.getByTestId("order-address");
  await expect(address).toContainText("sao paulo");
  await expect(address).toContainText("SP");
  await expect(address).toContainText("03149");

  await expect(page.getByTestId("order-review")).toContainText("2/5 sao");
  await expect(page.getByTestId("order-review")).toContainText("Chegou atrasado.");
});

test("mốc hay phần nào đơn chưa có thì hiện là chưa có, phần còn lại vẫn đủ", async ({
  page,
}) => {
  await mockOrders(page);
  await page.goto(`/orders/${BARE_ID}`);

  await expect(page.getByTestId("order-detail-outcome")).toHaveText("Chưa có kết quả");
  await expect(page.getByTestId("timeline-purchased-at")).toHaveText("17:21 09/02/2018");
  for (const testId of [
    "timeline-payment-approved-at",
    "timeline-handed-to-carrier-at",
    "timeline-delivered-at",
    "stage-payment-approval",
    "stage-seller-handling",
    "stage-carrier-transit",
  ]) {
    await expect(page.getByTestId(testId)).toHaveText("Chưa có");
  }
  await expect(page.getByTestId("order-items-empty")).toBeVisible();
  await expect(page.getByTestId("order-payments-empty")).toBeVisible();
  await expect(page.getByTestId("order-review-empty")).toBeVisible();
  await expect(page.getByTestId("order-address")).toContainText("rio de janeiro");
  await expect(page.getByTestId("order-detail-error")).toHaveCount(0);
});

test("mã đơn không tồn tại thì báo rõ không tìm thấy", async ({ page }) => {
  await mockOrders(page);
  await page.goto("/orders/khong-co-don-nay");

  await expect(page.getByTestId("order-detail-not-found")).toHaveText(
    "Không tìm thấy đơn “khong-co-don-nay”.",
  );
  await expect(page.getByTestId("order-detail-error")).toHaveCount(0);
});

test("đang ở trang 3 của danh sách đã lọc và sắp xếp, mở một đơn rồi Back thì về đúng chỗ cũ", async ({
  page,
}) => {
  const listCalls = await mockOrders(page);
  const listPath = "/orders?order_status=delivered&customer_state=SP&sort=order_value&direction=asc&page=3";
  await page.goto(listPath);
  await expect(page.getByTestId("orders-page-input")).toHaveValue("3");

  await page.getByTestId("order-id").first().click();
  await expect(page.getByTestId("order-detail-id")).toHaveText(LATE_ID);

  await page.goBack();

  await expect(page).toHaveURL(listPath);
  await expect(page.getByTestId("orders-page-input")).toHaveValue("3");
  await expect(page.getByTestId("filter-order-status")).toContainText("Đã giao");
  const last = listCalls.at(-1)!;
  expect(last.searchParams.get("page")).toBe("3");
  expect(last.searchParams.get("sort")).toBe("order_value");
  expect(last.searchParams.get("direction")).toBe("asc");
  expect(last.searchParams.get("order_status")).toBe("delivered");
  expect(last.searchParams.get("customer_state")).toBe("SP");
});

test("màn hình hẹp thì nội dung xếp một cột, không phải cuộn ngang", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockOrders(page);
  await page.goto(`/orders/${LATE_ID}`);
  await expect(page.getByTestId("order-item").first()).toBeVisible();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);

  const timeline = await page.getByTestId("order-timeline").boundingBox();
  const items = await page.getByTestId("order-items").boundingBox();
  expect(items!.y).toBeGreaterThan(timeline!.y + timeline!.height - 1);
  expect(Math.abs(items!.x - timeline!.x)).toBeLessThan(1);
});

test("đổi sang tiếng Anh thì mọi nhãn mới của trang chi tiết đổi theo", async ({
  page,
  context,
}) => {
  await context.addCookies([{ name: "NEXT_LOCALE", value: "en", url: "http://localhost:3000" }]);
  await mockOrders(page);
  await page.goto(`/orders/${BARE_ID}`);

  await expect(page.getByText("Timeline")).toBeVisible();
  await expect(page.getByTestId("timeline-delivered-at")).toHaveText("Not yet");
  await expect(page.getByTestId("order-review-empty")).toHaveText("No review for this order yet.");
});
