import { test, expect } from "@playwright/test";

import { mockSession } from "./session";

// Giả lập /model-metrics thay vì chạy thật (khác model-metrics.spec.ts): dữ liệu Olist
// thật luôn có cả hai lớp nhãn nên roc_auc không bao giờ null trong một lần chạy thật —
// nhánh "chưa có dữ liệu" (AC #3 của #42) chỉ chạm được bằng dữ liệu giả lập.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

const CHECKPOINT_METRICS = {
  precision: 0.5,
  recall: 0.5,
  f1: 0.5,
  accuracy: 0.6,
  roc_auc: 0.75,
};

const MODEL_METRICS_RESPONSE = {
  trained: true,
  report: {
    model_version: "20240101T000000Z",
    trained_at: "2024-01-01T00:00:00+00:00",
    selected_algorithm: "xgboost_quantile",
    f1_target: 0.3,
    f1_at_order_placed: 0.5,
    meets_f1_target: true,
    algorithms: {
      xgboost_quantile: {
        // Mốc order_placed không tính được ROC-AUC — tập chỉ còn một lớp nhãn.
        order_placed: { ...CHECKPOINT_METRICS, roc_auc: null },
        payment_approved: CHECKPOINT_METRICS,
        handed_to_carrier: CHECKPOINT_METRICS,
      },
    },
  },
  risk_threshold: 0.5,
  reconciliation: [
    { checkpoint: "order_placed", total: 10, correct: 6, incorrect: 4, precision: 0.6, recall: 0.6, accuracy: 0.6, small_sample: true },
    { checkpoint: "payment_approved", total: 10, correct: 6, incorrect: 4, precision: 0.6, recall: 0.6, accuracy: 0.6, small_sample: true },
    { checkpoint: "handed_to_carrier", total: 0, correct: 0, incorrect: 0, precision: null, recall: null, accuracy: null, small_sample: true },
  ],
};

test.beforeEach(async ({ context }) => {
  await context.addCookies([
    { name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" },
  ]);
  await mockSession(context);
  await context.route(`${BACKEND_URL}/model-metrics`, (route) =>
    route.fulfill({ json: MODEL_METRICS_RESPONSE }),
  );
});

test("ROC-AUC hiện \"chưa có dữ liệu\" khi mốc chỉ có một lớp nhãn, thay vì làm hỏng trang", async ({
  page,
}) => {
  await page.goto("/model-metrics");

  await expect(page.getByTestId("model-metrics-algorithm-row").first()).toContainText(
    "chưa có dữ liệu",
  );
  // Đối chiếu tích lũy hiển thị dấu gạch ngang cho accuracy rỗng, không phải văn bản này —
  // hai cách trình bày khác nhau có chủ đích cho hai quần thể khác nhau.
  await expect(
    page.getByTestId("reconciliation-row").filter({ hasText: "Đã bàn giao vận chuyển" }),
  ).not.toContainText("chưa có dữ liệu");
});
