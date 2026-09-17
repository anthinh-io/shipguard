import { apiFetch } from "./api";
import type { FieldError } from "./orders-api";

// Phải đọc nguyên dạng tĩnh như thế này thì Next mới thay được giá trị lúc build.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

export type Milestone = "payment_approved" | "handed_to_carrier" | "delivered_to_customer";

// Trang luôn gọi lại GET /orders/{id} (và /risk-assessments) sau khi một thao tác thành
// công (order-detail.tsx), nên các hàm dưới đây không cần trả về nội dung phản hồi — chỉ
// cần phân loại kết quả.
export type LifecycleActionResult =
  | { kind: "ok" }
  | { kind: "invalid"; errors: FieldError[] }
  // Gộp cả sáu mã 409 của LifecycleConflictError vào một loại: mọi mã đều có cùng cách
  // khắc phục duy nhất — trang đang cũ, tải lại — nên giao diện không cần phân biệt.
  | { kind: "conflict"; code: string; message: string }
  | { kind: "modelNotReady" }
  | { kind: "unreachable" };

async function requestLifecycleAction(
  url: string,
  init: RequestInit,
): Promise<LifecycleActionResult> {
  let response: Response;
  try {
    response = await apiFetch(url, init);
  } catch {
    return { kind: "unreachable" };
  }
  if (response.status === 422) {
    const { detail } = (await response.json()) as { detail: FieldError[] };
    return { kind: "invalid", errors: detail };
  }
  if (response.status === 409) {
    const { detail } = (await response.json()) as { detail: { code: string; message: string } };
    return { kind: "conflict", code: detail.code, message: detail.message };
  }
  if (response.status === 503) {
    return { kind: "modelNotReady" };
  }
  if (!response.ok) {
    return { kind: "unreachable" };
  }
  return { kind: "ok" };
}

export async function recordMilestone(
  orderId: string,
  milestone: Milestone,
  recordedAtIso: string,
): Promise<LifecycleActionResult> {
  return requestLifecycleAction(`${BACKEND_URL}/orders/${encodeURIComponent(orderId)}/milestones`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ milestone, recorded_at: recordedAtIso }),
  });
}

export async function editMilestoneTimestamp(
  orderId: string,
  milestone: Milestone,
  recordedAtIso: string,
): Promise<LifecycleActionResult> {
  return requestLifecycleAction(
    `${BACKEND_URL}/orders/${encodeURIComponent(orderId)}/milestones/${milestone}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ recorded_at: recordedAtIso }),
    },
  );
}

export async function cancelOrder(orderId: string): Promise<LifecycleActionResult> {
  return requestLifecycleAction(
    `${BACKEND_URL}/orders/${encodeURIComponent(orderId)}/cancellation`,
    { method: "POST" },
  );
}
