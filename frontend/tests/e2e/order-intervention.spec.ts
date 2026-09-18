import { test, expect, type Page } from "@playwright/test";

import { mockSession } from "./session";

// Trình duyệt gọi thẳng backend (ADR-0002). Endpoint ghi nhận Intervention nằm ở cấp gốc
// theo mã lần đánh giá (backend/app/api/routes/orders.py), không dưới /orders — nên cần một
// mẫu chặn riêng, khác ORDERS_API của order-lifecycle.spec.ts.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const ORDERS_API = `${BACKEND_URL}/orders**`;
const INTERVENTION_API = `${BACKEND_URL}/risk-assessments/**`;

const ORDER_ID = "d0000000000000000000000000000002";

type InterventionFixture = {
  intervention: string;
  note: string | null;
  handled_by: string;
  handled_at: string;
};

type AssessmentFixture = {
  id: number;
  checkpoint: string;
  assessed_at: string;
  late_probability: number;
  is_high_risk: boolean;
  threshold_used: number;
  model_version: string;
  risk_cause: {
    stage: string;
    seller_id: string | null;
    median_days: number;
    historical_median_days: number;
    excess_days: number;
  };
  was_correct: boolean | null;
  needs_handling: boolean;
  intervention: InterventionFixture | null;
};

function baseAssessment(overrides: Partial<AssessmentFixture> = {}): AssessmentFixture {
  return {
    id: 1,
    checkpoint: "order_placed",
    assessed_at: "2018-02-09T17:21:10+00:00",
    late_probability: 0.82,
    is_high_risk: true,
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
    needs_handling: true,
    intervention: null,
    ...overrides,
  };
}

function baseOrder() {
  return {
    order_id: ORDER_ID,
    order_status: "created",
    delivery_outcome: "no_outcome",
    order_value: 120.5,
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
    next_milestone: "payment_approved",
    cancelable: true,
  };
}

type MockState = { order: ReturnType<typeof baseOrder>; history: AssessmentFixture[] };

// Mock có trạng thái, cùng cách order-lifecycle.spec.ts mô phỏng order-detail.tsx tải lại
// toàn bộ đơn + lịch sử sau mỗi thao tác thành công thay vì vá cục bộ.
async function mockInterventionOrder(page: Page, state: MockState) {
  await page.route(ORDERS_API, (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === `/orders/${state.order.order_id}/notes`) {
      return route.fulfill({ json: [] });
    }
    if (url.pathname === `/orders/${state.order.order_id}/risk-assessments`) {
      return route.fulfill({ json: [...state.history].sort((a, b) => b.id - a.id) });
    }
    if (url.pathname === `/orders/${state.order.order_id}`) {
      return route.fulfill({ json: state.order });
    }
    return route.fulfill({ status: 404, json: { detail: "Order not found" } });
  });

  await page.route(INTERVENTION_API, (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const match = /^\/risk-assessments\/(\d+)\/intervention$/.exec(url.pathname);
    if (request.method() !== "POST" || !match) {
      return route.fulfill({ status: 404, json: { detail: "Not found" } });
    }
    const id = Number(match[1]);
    const target = state.history.find((assessment) => assessment.id === id);
    if (!target) {
      return route.fulfill({ status: 404, json: { detail: "Risk assessment not found" } });
    }
    const body = request.postDataJSON() as { intervention: string; note: string };
    target.intervention = {
      intervention: body.intervention,
      note: body.note.trim() === "" ? null : body.note.trim(),
      handled_by: "Nguyễn Lan",
      handled_at: "2018-02-09T18:00:00+00:00",
    };
    target.needs_handling = false;
    return route.fulfill({ status: 201, json: target });
  });
}

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" }]);
  await mockSession(context);
  await context.route(`${BACKEND_URL}/customer-states`, (route) => route.fulfill({ json: ["RJ", "SP"] }));
});

test("đánh giá rủi ro cao chưa xử lý: ghi nhận biện pháp thì hiện đầy đủ người xử lý và thời điểm", async ({
  page,
}) => {
  const state: MockState = { order: baseOrder(), history: [baseAssessment()] };
  await mockInterventionOrder(page, state);

  await page.goto(`/orders/${ORDER_ID}`);

  await expect(page.getByTestId("intervention-open")).toBeVisible();
  await page.getByTestId("intervention-open").click();
  await expect(page.getByTestId("intervention-dialog")).toBeVisible();

  await page.getByTestId("intervention-type").click();
  await page.getByRole("option", { name: "Nhắc hoặc ưu tiên người bán" }).click();
  await page.getByTestId("intervention-note").fill("Đã nhắc người bán ưu tiên đóng gói.");
  await page.getByTestId("intervention-submit").click();

  await expect(page.getByTestId("intervention-dialog")).toBeHidden();
  await expect(page.getByTestId("intervention-open")).toHaveCount(0);
  await expect(page.getByTestId("risk-assessment-intervention-type")).toHaveText(
    "Nhắc hoặc ưu tiên người bán",
  );
  await expect(page.getByTestId("risk-assessment-intervention-note")).toHaveText(
    "Đã nhắc người bán ưu tiên đóng gói.",
  );
  await expect(page.getByTestId("risk-assessment-intervention-handled-by")).toContainText(
    "Nguyễn Lan",
  );
});

test("đánh giá rủi ro thấp: không có nút ghi nhận xử lý", async ({ page }) => {
  const state: MockState = {
    order: baseOrder(),
    history: [baseAssessment({ is_high_risk: false, needs_handling: false })],
  };
  await mockInterventionOrder(page, state);

  await page.goto(`/orders/${ORDER_ID}`);

  await expect(page.getByTestId("risk-assessment-level")).toBeVisible();
  await expect(page.getByTestId("intervention-open")).toHaveCount(0);
});

test("ghi chú vượt 2.000 ký tự bị chặn trước khi gửi", async ({ page }) => {
  const state: MockState = { order: baseOrder(), history: [baseAssessment()] };
  await mockInterventionOrder(page, state);

  await page.goto(`/orders/${ORDER_ID}`);
  await page.getByTestId("intervention-open").click();
  await page.getByTestId("intervention-type").click();
  await page.getByRole("option", { name: "Khác", exact: true }).click();
  // Chuỗi có khoảng trắng xen kẽ, không phải một từ liền 2001 ký tự: field-sizing: content
  // của Textarea đo theo bề rộng nội dung lớn nhất có thể ngắt dòng — một từ không ngắt được
  // buộc trình duyệt giãn hộp theo chiều ngang thay vì cuộn dọc như dự kiến.
  await page.getByTestId("intervention-note").fill("a ".repeat(1001));
  await page.getByTestId("intervention-submit").click();

  await expect(page.getByText("Ghi chú không được dài quá 2.000 ký tự.")).toBeVisible();
  await expect(page.getByTestId("intervention-dialog")).toBeVisible();
});

test("lịch sử đánh giá: dòng đã xử lý hiện badge biện pháp", async ({ page }) => {
  const state: MockState = {
    order: baseOrder(),
    history: [
      baseAssessment({ id: 2, checkpoint: "handed_to_carrier" }),
      baseAssessment({
        id: 1,
        checkpoint: "order_placed",
        needs_handling: false,
        intervention: {
          intervention: "notify_customer",
          note: null,
          handled_by: "Nguyễn Lan",
          handled_at: "2018-02-09T17:30:00+00:00",
        },
      }),
    ],
  };
  await mockInterventionOrder(page, state);

  await page.goto(`/orders/${ORDER_ID}`);

  await expect(page.getByTestId("risk-assessment-history-intervention")).toHaveText(
    "Đã xử lý: Thông báo khách",
  );
});
