import { test, expect, type Page } from "@playwright/test";

import { mockSession } from "./session";

// Trình duyệt gọi thẳng backend (ADR-0002), nên mẫu chặn phải bám địa chỉ backend chứ
// không phải địa chỉ của trang.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const ORDERS_API = `${BACKEND_URL}/orders**`;

const ORDER_ID = "d0000000000000000000000000000001";

// Múi giờ phía đông UTC: mốc của đơn theo quy ước UTC không múi giờ của order-detail.spec.ts
// (purchased_at: "2018-02-09T17:21:04") phải quy đổi đúng sang giờ địa phương trên ô nhập,
// và giá trị nhập ở giờ địa phương phải gửi lên đúng thời điểm UTC — lệch một trong hai
// chiều là lệch cả ngày ở múi giờ này.
test.use({ timezoneId: "Asia/Ho_Chi_Minh" });

type OrderFixture = {
  order_id: string;
  order_status: string;
  delivery_outcome: string;
  order_value: number | null;
  timeline: {
    purchased_at: string;
    payment_approved_at: string | null;
    handed_to_carrier_at: string | null;
    delivered_at: string | null;
    estimated_delivery_date: string;
    payment_approval_days: number | null;
    seller_handling_days: number | null;
    carrier_transit_days: number | null;
  };
  address: { customer_city: string | null; customer_state: string; customer_zip_code_prefix: string | null };
  items: unknown[];
  sellers: unknown[];
  payments: unknown[];
  reviews: unknown[];
  next_milestone: string | null;
  cancelable: boolean;
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
};

function baseOrder(overrides: Partial<OrderFixture> = {}): OrderFixture {
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
    ...overrides,
  };
}

function baseAssessment(overrides: Partial<AssessmentFixture> = {}): AssessmentFixture {
  return {
    id: 1,
    checkpoint: "order_placed",
    assessed_at: "2018-02-09T17:21:10+00:00",
    late_probability: 0.2,
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
    ...overrides,
  };
}

type MockState = { order: OrderFixture; history: AssessmentFixture[] };

// Cùng quy ước lưu trữ của backend (_to_naive_utc, order_lifecycle.py): cắt phần offset,
// giữ nguyên giờ UTC — để Timeline (utcTimestamp) hiện lại đúng giờ đã ghi.
function toNaiveUtcString(iso: string): string {
  return new Date(iso).toISOString().slice(0, 19);
}

function applyMilestone(state: MockState, milestone: string, recordedAt: string, nextId: () => number) {
  const naive = toNaiveUtcString(recordedAt);
  if (milestone === "payment_approved") {
    state.order.timeline.payment_approved_at = naive;
    state.order.order_status = "approved";
    state.order.next_milestone = "handed_to_carrier";
  } else if (milestone === "handed_to_carrier") {
    state.order.timeline.handed_to_carrier_at = naive;
    state.order.order_status = "shipped";
    state.order.next_milestone = "delivered_to_customer";
  } else if (milestone === "delivered_to_customer") {
    state.order.timeline.delivered_at = naive;
    state.order.order_status = "delivered";
    state.order.next_milestone = null;
    state.order.cancelable = false;
    state.order.delivery_outcome = "on_time";
    // Reconciliation: điền was_correct cho mọi dòng cũ, không sinh dòng mới.
    state.history = state.history.map((a) => ({ ...a, was_correct: !a.is_high_risk }));
    return;
  }
  state.history = [
    { ...baseAssessment(), id: nextId(), checkpoint: milestone, assessed_at: recordedAt, was_correct: null },
    ...state.history,
  ];
}

function applyEdit(state: MockState, milestone: string, recordedAt: string, nextId: () => number) {
  const naive = toNaiveUtcString(recordedAt);
  if (milestone === "payment_approved") {
    state.order.timeline.payment_approved_at = naive;
  } else if (milestone === "handed_to_carrier") {
    state.order.timeline.handed_to_carrier_at = naive;
  }
  state.history = [
    { ...baseAssessment(), id: nextId(), checkpoint: milestone, assessed_at: recordedAt, was_correct: null },
    ...state.history,
  ];
}

// Mock có trạng thái: POST/PATCH/cancellation sửa `state` tại chỗ, GET sau đó đọc lại từ
// đây — mô phỏng đúng việc order-detail.tsx tải lại toàn bộ đơn và lịch sử sau mỗi thao
// tác thành công (không phải chèn cục bộ). Không dùng chung state với order-detail.spec.ts/
// create-order.spec.ts: các bài đó dùng hằng số cấp module cho chín bài test khác, biến
// chúng có trạng thái sẽ rò rỉ giữa các bài không liên quan.
async function mockLifecycleOrder(page: Page, state: MockState): Promise<{ postDataCalls: unknown[] }> {
  const postDataCalls: unknown[] = [];
  let nextAssessmentId = Math.max(0, ...state.history.map((a) => a.id)) + 1;

  await page.route(ORDERS_API, (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();

    if (method === "POST" && url.pathname === `/orders/${state.order.order_id}/milestones`) {
      const body = request.postDataJSON() as { milestone: string; recorded_at: string };
      postDataCalls.push(body);
      applyMilestone(state, body.milestone, body.recorded_at, () => nextAssessmentId++);
      return route.fulfill({ status: 201, json: {} });
    }
    if (method === "PATCH" && /^\/orders\/[^/]+\/milestones\/[^/]+$/.test(url.pathname)) {
      const milestone = url.pathname.split("/").pop() ?? "";
      const body = request.postDataJSON() as { recorded_at: string };
      postDataCalls.push(body);
      applyEdit(state, milestone, body.recorded_at, () => nextAssessmentId++);
      return route.fulfill({ status: 200, json: {} });
    }
    if (method === "POST" && url.pathname === `/orders/${state.order.order_id}/cancellation`) {
      state.order.order_status = "canceled";
      state.order.next_milestone = null;
      state.order.cancelable = false;
      return route.fulfill({
        status: 201,
        json: { order_id: state.order.order_id, order_status: "canceled" },
      });
    }
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

  return { postDataCalls };
}

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" }]);
  await mockSession(context);
  await context.route(`${BACKEND_URL}/customer-states`, (route) => route.fulfill({ json: ["RJ", "SP"] }));
});

test("đơn Olist lịch sử: khối mốc không có nút nào", async ({ page }) => {
  const state: MockState = {
    order: baseOrder({ order_status: "delivered", next_milestone: null, cancelable: false }),
    history: [],
  };
  await mockLifecycleOrder(page, state);

  await page.goto(`/orders/${ORDER_ID}`);

  await expect(page.getByTestId("milestone-actions-empty")).toBeVisible();
  await expect(page.getByTestId("order-milestone-actions").getByRole("button")).toHaveCount(0);
});

test("đơn đã giao: khối mốc không có nút nào, lịch sử hiện rõ đúng/sai", async ({ page }) => {
  const state: MockState = {
    order: baseOrder({
      order_status: "delivered",
      next_milestone: null,
      cancelable: false,
      delivery_outcome: "late",
    }),
    history: [
      baseAssessment({ id: 2, checkpoint: "handed_to_carrier", is_high_risk: true, was_correct: true }),
      baseAssessment({ id: 1, checkpoint: "order_placed", is_high_risk: false, was_correct: false }),
    ],
  };
  await mockLifecycleOrder(page, state);

  await page.goto(`/orders/${ORDER_ID}`);

  await expect(page.getByTestId("order-milestone-actions").getByRole("button")).toHaveCount(0);
  await expect(page.getByTestId("risk-assessment-outcome")).toHaveText("Đúng");
  await expect(page.getByTestId("risk-assessment-history-outcome")).toHaveText("Sai");
});

test("đơn mới tạo: ghi nhận duyệt thanh toán thì trạng thái đổi, lịch sử có thêm một dòng ngay, và giờ hiện đúng ngày UTC", async ({
  page,
}) => {
  const state: MockState = { order: baseOrder(), history: [baseAssessment()] };
  const { postDataCalls } = await mockLifecycleOrder(page, state);

  await page.goto(`/orders/${ORDER_ID}`);

  await expect(page.getByTestId("order-detail-status")).toHaveText("Mới tạo");
  await expect(page.getByTestId("milestone-edit-open")).toHaveCount(0);

  // purchased_at "2018-02-09T17:21:04" (UTC, không múi giờ) hiện thành "2018-02-10T00:21"
  // trên ô nhập ở +07 — sai chiều quy đổi này thì min lệch cả ngày.
  await expect(page.getByTestId("milestone-record-input")).toHaveAttribute("min", "2018-02-10T00:21");

  // Nhập "2018-02-10T01:00" giờ địa phương (+07) — quy đổi UTC là "2018-02-09T18:00", một
  // ngày lịch KHÁC với ngày đã nhập. Timeline vẫn phải hiện đúng "09/02", không phải "10/02".
  await page.getByTestId("milestone-record-input").fill("2018-02-10T01:00");
  await page.getByTestId("milestone-record-submit").click();

  await expect(page.getByTestId("order-detail-status")).toHaveText("Đã duyệt");
  await expect(page.getByTestId("timeline-payment-approved-at")).toHaveText("18:00 09/02/2018");

  expect(postDataCalls).toHaveLength(1);
  const call = postDataCalls[0] as { milestone: string; recorded_at: string };
  expect(call.milestone).toBe("payment_approved");
  expect(new Date(call.recorded_at).toISOString()).toBe("2018-02-09T18:00:00.000Z");

  // Lịch sử có thêm một dòng trên cùng ngay, không tải lại trang: dòng mới (payment_approved)
  // nổi bật, dòng cũ (order_placed) xuống danh sách bên dưới.
  await expect(page.getByTestId("risk-assessment-checkpoint")).toHaveText("Đã duyệt thanh toán");
  await expect(page.getByTestId("risk-assessment-history-row")).toHaveCount(1);
  await expect(page.getByTestId("risk-assessment-history-checkpoint")).toHaveText("Vừa đặt hàng");

  // Vừa ghi nhận payment_approved xong thì đã có một mốc để sửa.
  await expect(page.getByTestId("milestone-edit-open")).toBeVisible();
});

test("không nhập được thời điểm ở tương lai", async ({ page }) => {
  const state: MockState = { order: baseOrder(), history: [baseAssessment()] };
  const { postDataCalls } = await mockLifecycleOrder(page, state);

  await page.goto(`/orders/${ORDER_ID}`);

  await page.getByTestId("milestone-record-input").fill("2999-01-01T00:00");
  await page.getByTestId("milestone-record-submit").click();

  await expect(page.getByText("Thời điểm này không được ở tương lai.")).toBeVisible();
  expect(postDataCalls).toHaveLength(0);
});

test("đơn đã duyệt thanh toán: sửa lại thời điểm thì có thêm một lần đánh giá mới cùng điểm đánh giá", async ({
  page,
}) => {
  const state: MockState = {
    order: baseOrder({
      order_status: "approved",
      next_milestone: "handed_to_carrier",
      timeline: {
        purchased_at: "2018-02-09T17:21:04",
        payment_approved_at: "2018-02-10T02:00:00",
        handed_to_carrier_at: null,
        delivered_at: null,
        estimated_delivery_date: "2018-03-07",
        payment_approval_days: 0.3,
        seller_handling_days: null,
        carrier_transit_days: null,
      },
    }),
    history: [baseAssessment({ id: 2, checkpoint: "payment_approved" })],
  };
  const { postDataCalls } = await mockLifecycleOrder(page, state);

  await page.goto(`/orders/${ORDER_ID}`);
  await expect(page.getByTestId("risk-assessment-history-row")).toHaveCount(0);

  await page.getByTestId("milestone-edit-open").click();
  // Mốc trước đó (purchased_at) quy đổi ra +07 là "2018-02-10T00:21" — cùng min với ô ghi
  // nhận ở bài trên vì cùng dựa trên purchased_at.
  await expect(page.getByTestId("milestone-edit-input")).toHaveAttribute("min", "2018-02-10T00:21");
  // Giá trị đang có (payment_approved_at "2018-02-10T02:00" UTC) hiện thành "09:00" ở +07.
  await expect(page.getByTestId("milestone-edit-input")).toHaveValue("2018-02-10T09:00");

  await page.getByTestId("milestone-edit-input").fill("2018-02-10T10:15");
  await page.getByTestId("milestone-edit-submit").click();

  expect(postDataCalls).toHaveLength(1);
  const call = postDataCalls[0] as { recorded_at: string };
  expect(new Date(call.recorded_at).toISOString()).toBe("2018-02-10T03:15:00.000Z");

  // Hai dòng liền kề cùng tên điểm đánh giá (payment_approved) — sửa mốc không đè dòng cũ.
  await expect(page.getByTestId("risk-assessment-checkpoint")).toHaveText("Đã duyệt thanh toán");
  await expect(page.getByTestId("risk-assessment-history-row")).toHaveCount(1);
  await expect(page.getByTestId("risk-assessment-history-checkpoint")).toHaveText("Đã duyệt thanh toán");
});

test("hủy đơn cần xác nhận trước khi thực sự hủy", async ({ page }) => {
  const state: MockState = { order: baseOrder(), history: [baseAssessment()] };
  const { postDataCalls } = await mockLifecycleOrder(page, state);

  await page.goto(`/orders/${ORDER_ID}`);

  await page.getByTestId("milestone-cancel-open").click();
  await expect(page.getByTestId("cancel-order-dialog")).toBeVisible();
  await page.getByRole("button", { name: "Giữ đơn" }).click();
  await expect(page.getByTestId("cancel-order-dialog")).toBeHidden();
  expect(postDataCalls).toHaveLength(0);
  await expect(page.getByTestId("order-detail-status")).toHaveText("Mới tạo");

  await page.getByTestId("milestone-cancel-open").click();
  await page.getByTestId("cancel-order-confirm").click();

  await expect(page.getByTestId("order-detail-status")).toHaveText("Đã hủy");
  await expect(page.getByTestId("order-milestone-actions").getByRole("button")).toHaveCount(0);
});
