import { test, expect, type Page } from "@playwright/test";

// Trình duyệt gọi thẳng backend (ADR-0002), nên mẫu chặn phải bám địa chỉ backend chứ
// không phải địa chỉ của trang. Hai endpoint là anh em, không lồng nhau — `**` vượt cả
// dấu gạch chéo nên `/dashboard**` sẽ nuốt mất `/dashboard/sellers` nếu đặt lồng.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const DASHBOARD_API = `${BACKEND_URL}/dashboard**`;
const SELLERS_API = `${BACKEND_URL}/sellers**`;

const BUSIEST_SELLER = "6560211a19b47992c3666cc44a7e94c0";

test.beforeEach(async ({ context }) => {
  await context.addCookies([
    { name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" },
  ]);
});

// smallSample là tham số chứ không suy ra từ deliveredOrders: ngưỡng 30 là quyết định
// của backend và được kiểm ở đó (test_small_sample_threshold_excludes_exactly_thirty).
// Tính lại nó ở đây thì bài test tự trả lời câu hỏi của chính nó, thay vì kiểm cái
// thuộc về frontend — rằng màn hình vẽ đúng cờ nhận được. Cùng phân công với độ mịn
// của biểu đồ xu hướng ở #9.
function bodyFor(deliveredOrders: number, smallSample = false) {
  return {
    reporting_period: { start_date: "2018-01-01", end_date: "2018-01-30" },
    filter_options: { customer_states: ["AL", "SP"] },
    kpis: {
      delivered_orders: deliveredOrders,
      late_orders: 2,
      on_time_rate: 0.9,
      payment_approval: { median_days: 0.01, p90_days: 1.44 },
      seller_handling: { median_days: 1.82, p90_days: 5.99 },
      carrier_transit: { median_days: 7.1, p90_days: 18.9 },
      late_related_low_review_rate: 0.32,
    },
    late_rate_trend: { granularity: "day", points: [] },
    late_rate_by_state: [
      {
        customer_state: "SP",
        delivered_orders: deliveredOrders,
        late_orders: 2,
        late_rate: 0.1,
      },
    ],
    small_sample: smallSample,
    // Ba khối của #13 luôn có mặt trong phản hồi thật, kể cả khi không so sánh; giữ
    // chúng ở đây để mẫu giả không mô tả một phản hồi mà backend không tạo ra được.
    comparison_period: null,
    comparison_kpis: null,
    comparison_late_rate_trend: null,
  };
}

const SUGGESTIONS = [
  {
    seller_id: BUSIEST_SELLER,
    seller_city: "sao paulo",
    seller_state: "SP",
    delivered_orders: 42,
  },
  {
    seller_id: "4a3ca9315b744ce9f8e9374361493884",
    seller_city: "ibitinga",
    seller_state: "SP",
    delivered_orders: 7,
  },
];

async function mockSellers(page: Page): Promise<string[]> {
  const queries: string[] = [];
  await page.route(SELLERS_API, (route) => {
    const url = new URL(route.request().url());
    queries.push(url.searchParams.get("q") ?? "");
    return route.fulfill({ json: SUGGESTIONS });
  });
  return queries;
}

test("gõ dần ra gợi ý, mỗi dòng kèm bang và số đơn", async ({ page }) => {
  await page.route(DASHBOARD_API, (route) => route.fulfill({ json: bodyFor(75548) }));
  const queries = await mockSellers(page);

  await page.goto("/");
  await page.getByTestId("filter-seller").click();
  await page.getByTestId("filter-seller-input").fill("sao");

  const options = page.getByTestId("seller-option");
  await expect(options).toHaveCount(2);
  // Mã băm trông giống hệt nhau; bang, thành phố và số đơn là thứ phân biệt được.
  await expect(options.first()).toContainText("SP");
  await expect(options.first()).toContainText("sao paulo");
  await expect(options.first()).toContainText("42");
  await expect(options.nth(1)).toContainText("ibitinga");
  await expect(options.nth(1)).toContainText("7");
  // Gõ dần: chuỗi đang gõ đi tới máy chủ, không phải lọc một danh sách đầy đủ ở client.
  expect(queries).toContain("sao");
});

test("chọn một người bán sinh đúng một lần gọi mới mang seller_id", async ({ page }) => {
  const calls: string[] = [];
  await page.route(DASHBOARD_API, (route) => {
    const url = new URL(route.request().url());
    calls.push(url.search);
    const seller = url.searchParams.get("seller_id");
    return route.fulfill({ json: bodyFor(seller ? 42 : 75548) });
  });
  await mockSellers(page);

  await page.goto("/");
  await expect(page.getByTestId("kpi-grid")).toBeVisible();
  expect(calls).toHaveLength(1);

  await page.getByTestId("filter-seller").click();
  await page.getByTestId("filter-seller-input").fill("sao");
  await page.getByTestId("seller-option").first().click();

  await expect.poll(() => calls.length).toBe(2);
  expect(calls[1]).toContain(`seller_id=${BUSIEST_SELLER}`);
  await expect(page.getByTestId("kpi-on-time-rate")).toContainText("42");
});

test("người bán và bang lọc được cùng lúc trong một lần gọi", async ({ page }) => {
  const calls: string[] = [];
  await page.route(DASHBOARD_API, (route) => {
    const url = new URL(route.request().url());
    calls.push(url.search);
    return route.fulfill({ json: bodyFor(42) });
  });
  await mockSellers(page);

  await page.goto("/");
  await page.getByTestId("filter-customer-state").click();
  await page.getByRole("option", { name: "SP" }).click();
  await expect.poll(() => calls.length).toBe(2);

  await page.getByTestId("filter-seller").click();
  await page.getByTestId("filter-seller-input").fill("sao");
  await page.getByTestId("seller-option").first().click();

  await expect.poll(() => calls.length).toBe(3);
  // Hai chiều lọc cùng có mặt, và vẫn chỉ một lần gọi cho lần đổi này.
  expect(calls[2]).toContain("customer_state=SP");
  expect(calls[2]).toContain(`seller_id=${BUSIEST_SELLER}`);
});

test("lọc vào người bán dưới 30 đơn thì nhãn cảnh báo hiện ra", async ({ page }) => {
  // Đúng chuỗi nhân quả mà tiêu chí của #12 mô tả: chọn người bán TRƯỚC, nhãn hiện ra
  // SAU. Mock cờ theo tham số seller_id để lần gọi đầu (chưa lọc) không có nhãn.
  await page.route(DASHBOARD_API, (route) => {
    const url = new URL(route.request().url());
    return route.fulfill({
      json: url.searchParams.has("seller_id")
        ? bodyFor(17, true)
        : bodyFor(75548, false),
    });
  });
  await mockSellers(page);

  await page.goto("/");
  await expect(page.getByTestId("kpi-grid")).toBeVisible();
  await expect(page.getByTestId("small-sample-warning")).toHaveCount(0);

  await page.getByTestId("filter-seller").click();
  await page.getByTestId("filter-seller-input").fill("sao");
  await page.getByTestId("seller-option").first().click();

  await expect(page.getByTestId("small-sample-warning")).toBeVisible();
  await expect(page.getByTestId("small-sample-warning")).toContainText("17");
  // Số liệu vẫn còn nguyên sau khi bị gắn cờ.
  await expect(page.getByTestId("kpi-grid")).toBeVisible();
});

test("tập dưới 30 đơn hiện nhãn cảnh báo mà vẫn giữ nguyên số liệu", async ({ page }) => {
  await page.route(DASHBOARD_API, (route) =>
    route.fulfill({ json: bodyFor(17, true) }),
  );
  await mockSellers(page);

  await page.goto("/");

  await expect(page.getByTestId("small-sample-warning")).toBeVisible();
  await expect(page.getByTestId("small-sample-warning")).toContainText("17");
  // Tiêu chí cốt lõi của #12: gắn cờ thì cảnh báo, không ẩn số liệu đi.
  await expect(page.getByTestId("kpi-grid")).toBeVisible();
  await expect(page.getByTestId("kpi-on-time-rate")).toContainText("90");
  await expect(page.getByTestId("late-rate-by-state")).toBeVisible();
  await expect(page.getByTestId("dashboard-empty")).toHaveCount(0);
});

test("cờ tắt thì không hiện nhãn cảnh báo dù số đơn nhỏ", async ({ page }) => {
  // Ranh giới nằm ở backend và được kiểm ở đó; đây khẳng định frontend vẽ đúng cờ nhận
  // được, không tự suy ra ngưỡng của riêng nó — nên mock cố ý gửi 30 đơn kèm cờ tắt.
  await page.route(DASHBOARD_API, (route) =>
    route.fulfill({ json: bodyFor(30, false) }),
  );
  await mockSellers(page);

  await page.goto("/");

  await expect(page.getByTestId("kpi-grid")).toBeVisible();
  await expect(page.getByTestId("small-sample-warning")).toHaveCount(0);
});
