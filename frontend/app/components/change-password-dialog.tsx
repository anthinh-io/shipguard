"use client";

import { useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";

import { changePassword, type ChangePasswordResult } from "@/app/lib/api";
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

type Failure = Exclude<ChangePasswordResult, "ok"> | "mismatch";

export function ChangePasswordDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslations("changePassword");
  const [submitting, setSubmitting] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [succeeded, setSucceeded] = useState(false);

  // Đóng là xóa trạng thái: mở lại lần sau không được thấy lỗi hay thông báo cũ. Các ô
  // nhập tự trống vì DialogContent bị tháo khi đóng.
  function handleOpenChange(next: boolean) {
    if (!next) {
      setFailure(null);
      setSucceeded(false);
    }
    onOpenChange(next);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const newPassword = String(form.get("newPassword"));
    // Kiểm ở client vì máy chủ không nhận ô nhập lại. Không có quên mật khẩu qua email,
    // nên gõ nhầm mật khẩu mới là phải nhờ quản trị đặt lại.
    if (newPassword !== String(form.get("confirmPassword"))) {
      setFailure("mismatch");
      return;
    }
    setSubmitting(true);
    setFailure(null);
    const result = await changePassword(String(form.get("currentPassword")), newPassword);
    setSubmitting(false);
    if (result === "ok") {
      setSucceeded(true);
      return;
    }
    setFailure(result);
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      {/* Tắt nút X có sẵn: nhãn của nó là chữ "Close" viết cứng, không dịch được. */}
      <DialogContent data-testid="change-password-dialog" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
          <DialogDescription>{t("description")}</DialogDescription>
        </DialogHeader>
        {succeeded ? (
          <>
            <p data-testid="change-password-success" role="status">
              {t("success")}
            </p>
            <DialogFooter>
              <DialogClose asChild>
                <Button>{t("close")}</Button>
              </DialogClose>
            </DialogFooter>
          </>
        ) : (
          <form
            data-testid="change-password-form"
            onSubmit={handleSubmit}
            className="flex flex-col gap-4"
          >
            <label className="flex flex-col gap-1.5">
              <span>{t("currentPassword")}</span>
              <Input
                data-testid="change-password-current"
                name="currentPassword"
                type="password"
                autoComplete="current-password"
                required
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span>{t("newPassword")}</span>
              <Input
                data-testid="change-password-new"
                name="newPassword"
                type="password"
                autoComplete="new-password"
                required
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span>{t("confirmPassword")}</span>
              <Input
                data-testid="change-password-confirm"
                name="confirmPassword"
                type="password"
                autoComplete="new-password"
                required
              />
            </label>
            {failure ? (
              <p
                data-testid="change-password-error"
                role="alert"
                className="text-sm text-red-700 dark:text-red-400"
              >
                {t(failure)}
              </p>
            ) : null}
            <DialogFooter>
              <DialogClose asChild>
                <Button type="button" variant="outline">
                  {t("cancel")}
                </Button>
              </DialogClose>
              <Button data-testid="change-password-submit" type="submit" disabled={submitting}>
                {submitting ? t("submitting") : t("submit")}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
