"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { toLocalInputValue, utcTimestamp } from "@/app/lib/order-format";
import {
  cancelOrder,
  editMilestoneTimestamp,
  recordMilestone,
  type LifecycleActionResult,
  type Milestone,
} from "@/app/lib/order-lifecycle-api";
import { Section } from "./order-detail";
import { Button } from "./ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import { Input } from "./ui/input";

type MilestoneTimeline = {
  purchased_at: string;
  payment_approved_at: string | null;
  handed_to_carrier_at: string | null;
};

// Mốc trước đó của mỗi mốc, để suy min của ô nhập ("recorded_at không sớm hơn mốc trước",
// order_lifecycle.py:_validate_recorded_at). purchased_at luôn có giá trị nên nhánh
// payment_approved luôn có min; hai nhánh còn lại chỉ tới lượt khi mốc trước đã ghi.
function previousTimestamp(milestone: Milestone, timeline: MilestoneTimeline): string | null {
  switch (milestone) {
    case "payment_approved":
      return timeline.purchased_at;
    case "handed_to_carrier":
      return timeline.payment_approved_at;
    case "delivered_to_customer":
      return timeline.handed_to_carrier_at;
  }
}

// Mốc mới nhất còn sửa được — suy trực tiếp từ timeline, không từ order_status, để không
// thể suy ra một mốc không có cột thời điểm tương ứng. Không xét delivered_at: mốc giao
// không sửa được (order_lifecycle.py:edit_milestone chỉ nhận payment_approved/handed_to_carrier).
function latestEditableMilestone(
  timeline: MilestoneTimeline,
): "payment_approved" | "handed_to_carrier" | null {
  if (timeline.handed_to_carrier_at !== null) {
    return "handed_to_carrier";
  }
  if (timeline.payment_approved_at !== null) {
    return "payment_approved";
  }
  return null;
}

export function OrderMilestoneActions({
  orderId,
  nextMilestone,
  cancelable,
  timeline,
  refreshing,
  refreshFailed,
  onActionSucceeded,
}: {
  orderId: string;
  nextMilestone: Milestone | null;
  cancelable: boolean;
  timeline: MilestoneTimeline;
  // true từ lúc một thao tác thành công tới khi order-detail.tsx tải lại xong (thành công
  // hay thất bại) — nguồn sự thật duy nhất để giữ nút disabled, do order-detail.tsx quản lý
  // (không suy diễn tại đây từ việc so sánh timeline/refreshFailed đổi hay không).
  refreshing: boolean;
  // true khi lần gọi lại sau thao tác cuối không tải được — chỉ chọn câu thông báo.
  refreshFailed: boolean;
  onActionSucceeded: () => void;
}) {
  const t = useTranslations("orderDetail");

  // Chốt một lần lúc mount, như create-order-form.tsx: max không đuổi theo đồng hồ giữa
  // lúc mở form và lúc bấm nút.
  const [now] = useState(() => new Date());
  const nowInputValue = toLocalInputValue(now);

  const [recordValue, setRecordValue] = useState(nowInputValue);
  const [recordError, setRecordError] = useState<string | null>(null);

  const editableMilestone = latestEditableMilestone(timeline);
  const [editingOpen, setEditingOpen] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [editError, setEditError] = useState<string | null>(null);

  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  const [submitting, setSubmitting] = useState<"record" | "edit" | "cancel" | null>(null);

  // `refreshing` chuyển true → false đúng một lần mỗi chu kỳ tải lại: dùng cạnh xuống đó
  // (không phải việc refreshFailed đổi, dễ bị đọc nhầm khi một thao tác mới bắt đầu ngay
  // sau một lần thất bại) làm tín hiệu "đã xong" để đóng form sửa/dialog hủy, và xoá banner
  // xung đột (conflict) nếu lần tải lại đó thành công — banner đó chỉ còn đúng khi
  // refreshFailed, refreshing luôn true trước khi setSubmitting/setError của mỗi lần gửi
  // (xem handleRecord/handleEdit/handleCancel), nên lỗi đang hiện lúc refreshing tắt chỉ có
  // thể là banner xung đột, không phải lỗi hợp lệ hoá cục bộ. Chỉnh state ngay trong lúc
  // render (không qua effect) theo đúng cách React khuyến nghị để "điều chỉnh state khi
  // prop đổi" — tránh một lượt render thừa.
  const [seenRefreshing, setSeenRefreshing] = useState(refreshing);
  if (seenRefreshing !== refreshing) {
    setSeenRefreshing(refreshing);
    if (seenRefreshing && !refreshing) {
      setEditingOpen(false);
      setCancelDialogOpen(false);
      if (!refreshFailed) {
        setRecordError(null);
        setEditError(null);
        setCancelError(null);
      }
    }
  }

  const disabled = submitting !== null || refreshing;

  function minFor(milestone: Milestone): string | undefined {
    const previous = previousTimestamp(milestone, timeline);
    return previous === null ? undefined : toLocalInputValue(utcTimestamp(previous));
  }

  // Luật "không sớm hơn mốc trước" của recorded_at, chặn trước khi gửi — cùng lý do với
  // create-order-form.tsx: thông báo lỗi 422 của máy chủ là tiếng Anh thô, không dịch được.
  // Luật còn lại ("không ở tương lai") đọc Date.now() ngay trong handleRecord/handleEdit —
  // như create-order-form.tsx tự làm trong handleSubmit — không qua một hàm phụ ở đây, để
  // khỏi gọi một nguồn không thuần khiết từ một hàm mà React coi là có thể chạy lúc render.
  function validateNotBeforePrevious(value: string, min: string | undefined): string | null {
    return min !== undefined && value < min ? t("milestoneActions.errors.beforePrevious") : null;
  }

  function genericErrorMessage(result: LifecycleActionResult): string {
    if (result.kind === "invalid") {
      return result.errors[0]?.msg ?? t("milestoneActions.errors.unreachable");
    }
    if (result.kind === "conflict") {
      return t("milestoneActions.errors.conflict");
    }
    if (result.kind === "modelNotReady") {
      return t("milestoneActions.errors.modelNotReady");
    }
    return t("milestoneActions.errors.unreachable");
  }

  async function handleRecord(nowMs: number) {
    if (recordValue.trim() === "" || !nextMilestone) {
      return;
    }
    const min = minFor(nextMilestone);
    if (new Date(recordValue).getTime() > nowMs) {
      setRecordError(t("milestoneActions.errors.future"));
      return;
    }
    const validationError = validateNotBeforePrevious(recordValue, min);
    if (validationError) {
      setRecordError(validationError);
      return;
    }
    setRecordError(null);
    setSubmitting("record");
    const result = await recordMilestone(orderId, nextMilestone, new Date(recordValue).toISOString());
    setSubmitting(null);
    if (result.kind === "ok" || result.kind === "conflict") {
      setRecordError(result.kind === "conflict" ? genericErrorMessage(result) : null);
      onActionSucceeded();
      return;
    }
    setRecordError(genericErrorMessage(result));
  }

  function openEdit() {
    if (editableMilestone === null) {
      return;
    }
    const current =
      editableMilestone === "payment_approved"
        ? timeline.payment_approved_at
        : timeline.handed_to_carrier_at;
    if (current === null) {
      return;
    }
    setEditValue(toLocalInputValue(utcTimestamp(current)));
    setEditError(null);
    setEditingOpen(true);
  }

  async function handleEdit(nowMs: number) {
    if (editValue.trim() === "" || editableMilestone === null) {
      return;
    }
    const min = minFor(editableMilestone);
    if (new Date(editValue).getTime() > nowMs) {
      setEditError(t("milestoneActions.errors.future"));
      return;
    }
    const validationError = validateNotBeforePrevious(editValue, min);
    if (validationError) {
      setEditError(validationError);
      return;
    }
    setEditError(null);
    setSubmitting("edit");
    const result = await editMilestoneTimestamp(
      orderId,
      editableMilestone,
      new Date(editValue).toISOString(),
    );
    setSubmitting(null);
    if (result.kind === "ok" || result.kind === "conflict") {
      setEditError(result.kind === "conflict" ? genericErrorMessage(result) : null);
      onActionSucceeded();
      return;
    }
    setEditError(genericErrorMessage(result));
  }

  async function handleCancel() {
    setCancelError(null);
    setSubmitting("cancel");
    const result = await cancelOrder(orderId);
    setSubmitting(null);
    if (result.kind === "ok" || result.kind === "conflict") {
      setCancelError(result.kind === "conflict" ? genericErrorMessage(result) : null);
      onActionSucceeded();
      return;
    }
    setCancelError(genericErrorMessage(result));
  }

  // Boolean(...) chứ không so === null/=== true: dữ liệu giả lập của các bài test cũ
  // (order-detail.spec.ts, create-order.spec.ts, viết trước #33/#34) không có hai trường
  // này nên đọc thành undefined — phải coi như false/không có mốc, không phải một mốc thật
  // tên "undefined".
  const hasNextMilestone = Boolean(nextMilestone);
  const hasAnyAction = hasNextMilestone || Boolean(cancelable);

  return (
    <Section title={t("milestoneActions.title")} testId="order-milestone-actions">
      {refreshFailed ? (
        <p
          data-testid="milestone-actions-refresh-failed"
          className="mb-3 text-sm text-amber-700 dark:text-amber-400"
        >
          {t("milestoneActions.errors.refreshFailed")}
        </p>
      ) : null}
      {!hasAnyAction ? (
        <p data-testid="milestone-actions-empty" className="text-muted-foreground">
          {t("milestoneActions.noActions")}
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          {nextMilestone ? (
            <div className="flex flex-col gap-2">
              <h3 className="text-sm font-medium">
                {t("milestoneActions.record", {
                  milestone: t(`milestoneActions.milestones.${nextMilestone}`),
                })}
              </h3>
              <MilestoneTimeForm
                testIdPrefix="milestone-record"
                value={recordValue}
                onChange={setRecordValue}
                min={minFor(nextMilestone)}
                max={nowInputValue}
                submitLabel={t("milestoneActions.submit")}
                submitting={submitting === "record"}
                disabled={disabled}
                onSubmit={handleRecord}
                error={recordError}
              />
            </div>
          ) : null}

          {editableMilestone !== null ? (
            <div className="flex flex-col gap-2">
              <h3 className="text-sm font-medium">
                {t(`milestoneActions.milestones.${editableMilestone}`)}
              </h3>
              {editingOpen ? (
                <MilestoneTimeForm
                  testIdPrefix="milestone-edit"
                  value={editValue}
                  onChange={setEditValue}
                  min={minFor(editableMilestone)}
                  max={nowInputValue}
                  submitLabel={t("milestoneActions.submit")}
                  submitting={submitting === "edit"}
                  disabled={disabled}
                  onSubmit={handleEdit}
                  onCancel={() => setEditingOpen(false)}
                  error={editError}
                />
              ) : (
                <Button
                  data-testid="milestone-edit-open"
                  type="button"
                  variant="outline"
                  size="sm"
                  className="self-start"
                  disabled={disabled}
                  onClick={openEdit}
                >
                  {t("milestoneActions.edit")}
                </Button>
              )}
            </div>
          ) : null}

          {cancelable ? (
            <div>
              <Button
                data-testid="milestone-cancel-open"
                type="button"
                variant="destructive"
                size="sm"
                disabled={disabled}
                onClick={() => setCancelDialogOpen(true)}
              >
                {t("milestoneActions.cancelOrder")}
              </Button>
              {cancelError ? (
                <p role="alert" className="mt-2 text-sm text-red-700 dark:text-red-400">
                  {cancelError}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
      )}

      <Dialog
        open={cancelDialogOpen}
        onOpenChange={(open) => {
          if (!open) {
            setCancelDialogOpen(false);
          }
        }}
      >
        <DialogContent data-testid="cancel-order-dialog" showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>{t("milestoneActions.cancelDialog.title")}</DialogTitle>
            <DialogDescription>{t("milestoneActions.cancelDialog.description")}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline">
                {t("milestoneActions.cancelDialog.cancel")}
              </Button>
            </DialogClose>
            <Button
              data-testid="cancel-order-confirm"
              variant="destructive"
              disabled={disabled}
              onClick={handleCancel}
            >
              {t("milestoneActions.cancelDialog.confirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Section>
  );
}

// Dùng lại cho cả ghi nhận mốc kế tiếp và sửa mốc mới nhất: hai form giống nhau (nhãn + ô
// datetime-local + min/max + dòng lỗi + nút), chỉ khác giá trị khởi tạo và hàm gọi API.
function MilestoneTimeForm({
  testIdPrefix,
  value,
  onChange,
  min,
  max,
  submitLabel,
  submitting,
  disabled,
  onSubmit,
  onCancel,
  error,
}: {
  testIdPrefix: string;
  value: string;
  onChange: (value: string) => void;
  min?: string;
  max: string;
  submitLabel: string;
  submitting: boolean;
  disabled: boolean;
  // Nhận nowMs từ chính nơi bấm nút (native onClick dưới đây), không phải người gọi tự đọc
  // Date.now() bên trong một hàm xử lý — đó là cách React coi là an toàn để đọc một nguồn
  // không thuần khiết mà không bị nghi là "có thể chạy lúc render".
  onSubmit: (nowMs: number) => void;
  onCancel?: () => void;
  error: string | null;
}) {
  const t = useTranslations("orderDetail");

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1.5">
          <span className="text-sm">{t("milestoneActions.recordedAt")}</span>
          <Input
            data-testid={`${testIdPrefix}-input`}
            type="datetime-local"
            value={value}
            min={min}
            max={max}
            onChange={(event) => onChange(event.target.value)}
          />
        </label>
        <Button
          data-testid={`${testIdPrefix}-submit`}
          type="button"
          size="sm"
          disabled={disabled || value.trim() === ""}
          onClick={() => onSubmit(Date.now())}
        >
          {submitting ? t("milestoneActions.submitting") : submitLabel}
        </Button>
        {onCancel ? (
          <Button type="button" variant="outline" size="sm" disabled={submitting} onClick={onCancel}>
            {t("milestoneActions.cancelEdit")}
          </Button>
        ) : null}
      </div>
      {error ? (
        <p role="alert" className="text-sm text-red-700 dark:text-red-400">
          {error}
        </p>
      ) : null}
    </div>
  );
}
