import { test, expect, type BrowserContext, type Locator, type Page } from "@playwright/test";

import { mockSession } from "./session";

// Trình duyệt gọi thẳng backend (ADR-0002), nên mẫu chặn phải bám địa chỉ backend chứ
// không phải địa chỉ của trang.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const ORDERS_API = `${BACKEND_URL}/orders**`;

const SELLER_A = "3504c0cb71d7fa48d967e0e4c94d59d9";
const SELLER_B = "289cdb325fb7e7f891c38608bf9e0962";
const NEW_ORDER_ID = "c0ffee00000000000000000000000000";

const SELLERS = [
  { seller_id: SELLER_A, seller_city: "maua", seller_state: "SP", delivered_orders: 10 },
  { seller_id: SELLER_B, seller_city: "ibitinga", seller_state: "SP", delivered_orders: 5 },
];

const CATEGORIES = [
  { name: "housewares", label: "Housewares" },
  { name: "eletronicos", label: "Electronics" },
];

function orderDetailFixture() {
  return {
    order_id: NEW_ORDER_ID,
    order_status: "created",
    delivery_outcome: "no_outcome",
    order_value: 208.4,
    timeline: {
      purchased_at: "2026-09-17T08:00:00",
      payment_approved_at: null,
      handed_to_carrier_at: null,
      delivered_at: null,
      estimated_delivery_date: "2026-10-01",
      payment_approval_days: null,
      seller_handling_days: null,
      carrier_transit_days: null,
    },
    address: { customer_city: "sao paulo", customer_state: "SP", customer_zip_code_prefix: "03149" },
    items: [
      {
        order_item_id: 1,
        product_id: "p1",
        category: "housewares",
        price: 29.99,
        freight_value: 8.5,
        seller_id: SELLER_A,
      },
      {
        order_item_id: 2,
        product_id: "p2",
        category: "eletronicos",
        price: 199.9,
        freight_value: 15,
        seller_id: SELLER_B,
      },
    ],
    sellers: [
      { seller_id: SELLER_A, seller_city: "maua", seller_state: "SP" },
      { seller_id: SELLER_B, seller_city: "ibitinga", seller_state: "SP" },
    ],
    payments: [
      { payment_sequential: 1, payment_type: "credit_card", payment_installments: 3, payment_value: 100 },
      { payment_sequential: 2, payment_type: "voucher", payment_installments: 1, payment_value: 50 },
    ],
    reviews: [],
  };
}

function highRiskAssessment() {
  return [
    {
      id: 1,
      checkpoint: "payment_approved",
      assessed_at: "2026-09-17T08:05:00Z",
      late_probability: 0.87,
      is_high_risk: true,
      threshold_used: 0.5,
      model_version: "v1",
      risk_cause: {
        stage: "seller_handling",
        seller_id: SELLER_A,
        median_days: 5,
        historical_median_days: 2,
        excess_days: 3,
      },
      was_correct: null,
      needs_handling: true,
    },
  ];
}

function lowRiskAssessment() {
  return [
    {
      id: 2,
      checkpoint: "order_placed",
      assessed_at: "2026-09-17T08:05:00Z",
      late_probability: 0.12,
      is_high_risk: false,
      threshold_used: 0.5,
      model_version: "v1",
      risk_cause: {
        stage: "carrier_transit",
        seller_id: null,
        median_days: 3,
        historical_median_days: 3,
        excess_days: 0,
      },
      was_correct: null,
      needs_handling: false,
    },
  ];
}

async function mockCreateOrderDeps(context: BrowserContext) {
  await mockSession(context);
  await context.route(`${BACKEND_URL}/customer-states`, (route) =>
    route.fulfill({ json: ["RJ", "SP"] }),
  );
  await context.route(`${BACKEND_URL}/product-categories`, (route) =>
    route.fulfill({ json: CATEGORIES }),
  );
  await context.route(`${BACKEND_URL}/sellers**`, (route) => route.fulfill({ json: SELLERS }));
}

test.beforeEach(async ({ context }) => {
  await context.addCookies([
    { name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" },
  ]);
  await mockCreateOrderDeps(context);
});

async function pickOption(page: Page, trigger: Locator, name: string) {
  await trigger.click();
  await page.getByRole("option", { name, exact: true }).click();
}

// Combobox người bán dùng cổng chặn của radix-ui: nút bấm nằm trong dòng sản phẩm, nhưng
// PopoverContent (ô gõ và danh sách gợi ý) được portal ra ngoài — không nằm trong cây DOM
// của dòng đó nữa, nên phải thao tác qua locator cấp trang sau khi bấm đúng nút của dòng.
async function pickSeller(page: Page, row: Locator, optionIndex: number) {
  await row.getByTestId("filter-seller").click();
  await page.getByTestId("filter-seller-input").fill("s");
  await expect(page.getByTestId("seller-option")).toHaveCount(SELLERS.length);
  await page.getByTestId("seller-option").nth(optionIndex).click();
}

async function fillAddress(page: Page) {
  await pickOption(page, page.getByTestId("create-order-state"), "SP");
  await page.getByTestId("create-order-city").fill("sao paulo");
  await page.getByTestId("create-order-zip").fill("03149");
}

test("đường vui: đơn hai người bán và hai dòng thanh toán, gửi xong chuyển sang trang chi tiết với đúng dữ liệu mỗi dòng", async ({
  page,
}) => {
  let postBody: unknown = null;
  await page.route(ORDERS_API, (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (request.method() === "POST" && url.pathname === "/orders") {
      postBody = request.postDataJSON();
      return route.fulfill({ status: 201, json: { order_id: NEW_ORDER_ID } });
    }
    if (url.pathname === `/orders/${NEW_ORDER_ID}`) {
      return route.fulfill({ json: orderDetailFixture() });
    }
    if (url.pathname === `/orders/${NEW_ORDER_ID}/notes`) {
      return route.fulfill({ json: [] });
    }
    if (url.pathname === `/orders/${NEW_ORDER_ID}/risk-assessments`) {
      return route.fulfill({ json: highRiskAssessment() });
    }
    return route.fulfill({ status: 404, json: { detail: "Order not found" } });
  });

  await page.goto("/orders/new");
  await fillAddress(page);

  // Dòng sản phẩm 1.
  const items = page.getByTestId("create-order-item");
  await pickSeller(page, items.nth(0), 0);
  await pickOption(page, items.nth(0).getByTestId("create-order-category"), "Housewares");
  await items.nth(0).getByTestId("create-order-weight").fill("500");
  await items.nth(0).getByTestId("create-order-price").fill("29.99");
  await items.nth(0).getByTestId("create-order-freight").fill("8.5");

  // Thêm dòng sản phẩm thứ hai — người bán, danh mục, giá, phí phải là của riêng dòng này.
  await page.getByTestId("create-order-add-item").click();
  await expect(items).toHaveCount(2);
  await pickSeller(page, items.nth(1), 1);
  await pickOption(page, items.nth(1).getByTestId("create-order-category"), "Electronics");
  await items.nth(1).getByTestId("create-order-price").fill("199.90");
  await items.nth(1).getByTestId("create-order-freight").fill("15");
  // Cân nặng bỏ trống ở dòng này: phải gửi null, không phải kế thừa cân nặng dòng trên.

  // Dòng thanh toán 1: thẻ tín dụng, có trả góp.
  const payments = page.getByTestId("create-order-payment");
  await payments.nth(0).getByTestId("create-order-payment-amount").fill("100");
  await payments.nth(0).getByTestId("create-order-payment-installments").fill("3");

  // Thêm dòng thanh toán thứ hai: đổi sang phiếu mua hàng — số kỳ trả góp phải khoá về 1.
  await page.getByTestId("create-order-add-payment").click();
  await expect(payments).toHaveCount(2);
  await pickOption(page, payments.nth(1).getByTestId("create-order-payment-type"), "Phiếu mua hàng");
  await expect(payments.nth(1).getByTestId("create-order-payment-installments")).toBeDisabled();
  await expect(payments.nth(1).getByTestId("create-order-payment-installments")).toHaveValue("1");
  await payments.nth(1).getByTestId("create-order-payment-amount").fill("50");

  await page.getByTestId("create-order-submit").click();

  await expect(page).toHaveURL(new RegExp(`/orders/${NEW_ORDER_ID}$`));

  const body = postBody as {
    items: { seller_id: string; product_category_name: string; product_weight_g: number | null; price: number; freight_value: number }[];
    payments: { payment_type: string; payment_installments: number; payment_value: number }[];
  };
  expect(body.items).toHaveLength(2);
  expect(body.items[0]).toMatchObject({
    seller_id: SELLER_A,
    product_category_name: "housewares",
    product_weight_g: 500,
    price: 29.99,
    freight_value: 8.5,
  });
  expect(body.items[1]).toMatchObject({
    seller_id: SELLER_B,
    product_category_name: "eletronicos",
    product_weight_g: null,
    price: 199.9,
    freight_value: 15,
  });
  expect(body.payments).toHaveLength(2);
  expect(body.payments[0]).toMatchObject({
    payment_type: "credit_card",
    payment_installments: 3,
    payment_value: 100,
  });
  expect(body.payments[1]).toMatchObject({
    payment_type: "voucher",
    payment_installments: 1,
    payment_value: 50,
  });

  // Khối Risk Assessment của trang chi tiết vừa mở tới: rủi ro cao hiện đúng chặng, số
  // ngày lệch và người bán liên quan.
  await expect(page.getByTestId("risk-assessment-probability")).toContainText("87,00%");
  await expect(page.getByTestId("risk-assessment-badge")).toHaveText("Rủi ro cao");
  // Nhãn chặng nằm ở <dt>, giá trị "dự kiến/thường" nằm ở <dd data-testid=...> — kiểm cả
  // khối để chắc chắn đúng chặng gây rủi ro (seller_handling) được hiện, không phải chặng
  // khác.
  await expect(page.getByTestId("order-risk-assessment")).toContainText("Chặng người bán xử lý");
  await expect(page.getByTestId("risk-assessment-stage")).toContainText("Dự kiến 5 ngày, thường 2 ngày");
  await expect(page.getByTestId("risk-assessment-seller")).toContainText(SELLER_A);
  await expect(page.getByTestId("risk-assessment-seller")).toContainText("maua · SP");
});

test("số kỳ trả góp chỉ mở khi hình thức là thẻ tín dụng", async ({ page }) => {
  await page.goto("/orders/new");
  const payment = page.getByTestId("create-order-payment").first();
  const installments = payment.getByTestId("create-order-payment-installments");

  await expect(installments).toBeEnabled();
  await pickOption(page, payment.getByTestId("create-order-payment-type"), "Boleto");
  await expect(installments).toBeDisabled();
  await expect(installments).toHaveValue("1");
  await pickOption(page, payment.getByTestId("create-order-payment-type"), "Thẻ tín dụng");
  await expect(installments).toBeEnabled();
});

test("thêm rồi xoá dòng sản phẩm và thanh toán: số dòng đúng, dòng cuối cùng không xoá được", async ({
  page,
}) => {
  await page.goto("/orders/new");
  const items = page.getByTestId("create-order-item");
  const payments = page.getByTestId("create-order-payment");

  await expect(items).toHaveCount(1);
  await expect(items.first().getByTestId("create-order-remove-item")).toBeDisabled();
  await page.getByTestId("create-order-add-item").click();
  await expect(items).toHaveCount(2);
  await items.nth(1).getByTestId("create-order-remove-item").click();
  await expect(items).toHaveCount(1);

  await expect(payments).toHaveCount(1);
  await expect(payments.first().getByTestId("create-order-remove-payment")).toBeDisabled();
  await page.getByTestId("create-order-add-payment").click();
  await expect(payments).toHaveCount(2);
  await payments.nth(1).getByTestId("create-order-remove-payment").click();
  await expect(payments).toHaveCount(1);
});

test("để trống giá, phí vận chuyển hay số tiền thanh toán thì báo lỗi cạnh đúng ô, không âm thầm gửi giá trị 0", async ({
  page,
}) => {
  let postCount = 0;
  await page.route(ORDERS_API, (route) => {
    const request = route.request();
    if (request.method() === "POST" && new URL(request.url()).pathname === "/orders") {
      postCount += 1;
      return route.fulfill({ status: 201, json: { order_id: NEW_ORDER_ID } });
    }
    return route.fulfill({ status: 404, json: { detail: "Order not found" } });
  });

  await page.goto("/orders/new");
  await fillAddress(page);
  await page.getByTestId("create-order-city").fill("sao paulo");
  const items = page.getByTestId("create-order-item");
  await pickSeller(page, items.first(), 0);
  await pickOption(page, items.first().getByTestId("create-order-category"), "Housewares");
  // Cố ý bỏ trống giá, phí vận chuyển và số tiền thanh toán — form có noValidate nên
  // "required" của trình duyệt không tự chặn; Number("") ra 0 là một giá trị hợp lệ với
  // backend, nên phải tự kiểm rỗng ở trình duyệt trước khi parse, không dựa vào 422.

  await page.getByTestId("create-order-submit").click();

  await expect(page.getByTestId("create-order-error")).toHaveCount(0);
  await expect(page.getByText("Trường này không được để trống.")).toHaveCount(3);
  expect(postCount).toBe(0);
});

test("một trường sai (bang không hợp lệ) hiện lỗi cạnh đúng ô, các trường khác vẫn giữ nguyên", async ({
  page,
}) => {
  await page.route(ORDERS_API, (route) => {
    const request = route.request();
    if (request.method() === "POST" && new URL(request.url()).pathname === "/orders") {
      return route.fulfill({
        status: 422,
        json: {
          detail: [
            {
              type: "value_error",
              loc: ["body", "customer_state"],
              msg: "customer_state must be one of the 2 states that already have orders",
            },
          ],
        },
      });
    }
    return route.fulfill({ status: 404, json: { detail: "Order not found" } });
  });

  await page.goto("/orders/new");
  await fillAddress(page);
  await page.getByTestId("create-order-city").fill("sao paulo");

  const items = page.getByTestId("create-order-item");
  await pickSeller(page, items.first(), 0);
  await pickOption(page, items.first().getByTestId("create-order-category"), "Housewares");
  await items.first().getByTestId("create-order-price").fill("29.99");
  await items.first().getByTestId("create-order-freight").fill("8.5");
  await page.getByTestId("create-order-payment").first().getByTestId("create-order-payment-amount").fill("38.49");

  await page.getByTestId("create-order-submit").click();

  // Lỗi phải gắn đúng vào trường bang (byPath["customer_state"]), không rơi vào banner
  // chung đầu form — banner đó chỉ dành cho lỗi không trỏ được tới trường lá cụ thể.
  await expect(page.getByTestId("create-order-error")).toHaveCount(0);
  await expect(
    page.getByText("customer_state must be one of the 2 states that already have orders"),
  ).toBeVisible();
  // Trường khác vẫn còn nguyên giá trị đã nhập — một trường sai không xoá dữ liệu các
  // trường còn lại.
  await expect(page.getByTestId("create-order-city")).toHaveValue("sao paulo");
  await expect(items.first().getByTestId("create-order-price")).toHaveValue("29.99");
  await expect(page).toHaveURL(/\/orders\/new$/);
});

test("mô hình dự đoán rủi ro chưa sẵn sàng thì báo riêng, không gộp vào lỗi chung", async ({
  page,
}) => {
  await page.route(ORDERS_API, (route) => {
    const request = route.request();
    if (request.method() === "POST" && new URL(request.url()).pathname === "/orders") {
      return route.fulfill({ status: 503, json: { detail: "model not ready" } });
    }
    return route.fulfill({ status: 404, json: { detail: "Order not found" } });
  });

  await page.goto("/orders/new");
  await fillAddress(page);
  const items = page.getByTestId("create-order-item");
  await pickSeller(page, items.first(), 0);
  await pickOption(page, items.first().getByTestId("create-order-category"), "Housewares");
  await items.first().getByTestId("create-order-price").fill("29.99");
  await items.first().getByTestId("create-order-freight").fill("8.5");
  await page.getByTestId("create-order-payment").first().getByTestId("create-order-payment-amount").fill("38.49");

  await page.getByTestId("create-order-submit").click();

  await expect(page.getByTestId("create-order-error")).toHaveText(
    "Mô hình dự đoán rủi ro chưa sẵn sàng. Vui lòng thử lại sau.",
  );
});

test("chưa đăng nhập thì mở /orders/new bị đưa tới trang đăng nhập", async ({ page, context }) => {
  await context.route(`${BACKEND_URL}/auth/refresh`, (route) =>
    route.fulfill({ status: 401, json: { detail: "Invalid refresh token" } }),
  );

  await page.goto("/orders/new");

  await expect(page).toHaveURL("/login?next=%2Forders%2Fnew");
});

test("màn hình hẹp thì nội dung xếp một cột, không cuộn ngang", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/orders/new");

  await expect(page.getByTestId("create-order-item").first()).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test("khối rủi ro thấp không hiện chặng hay người bán gây rủi ro", async ({ page }) => {
  await page.route(ORDERS_API, (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === `/orders/${NEW_ORDER_ID}`) {
      return route.fulfill({ json: orderDetailFixture() });
    }
    if (url.pathname === `/orders/${NEW_ORDER_ID}/notes`) {
      return route.fulfill({ json: [] });
    }
    if (url.pathname === `/orders/${NEW_ORDER_ID}/risk-assessments`) {
      return route.fulfill({ json: lowRiskAssessment() });
    }
    return route.fulfill({ status: 404, json: { detail: "Order not found" } });
  });

  await page.goto(`/orders/${NEW_ORDER_ID}`);

  await expect(page.getByTestId("risk-assessment-badge")).toHaveText("Rủi ro thấp");
  await expect(page.getByTestId("risk-assessment-stage")).toHaveCount(0);
  await expect(page.getByTestId("risk-assessment-seller")).toHaveCount(0);
});
