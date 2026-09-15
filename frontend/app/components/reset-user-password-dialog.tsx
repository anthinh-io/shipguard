"use client";

import { useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";

import {
  resetUserPassword,
  type AdminUser,
  type ResetUserPasswordResult,
} from "@/app/lib/users-api";
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

type Failure = Exclude<ResetUserPasswordResult, "ok"> | "mismatch";

export function ResetUserPasswordDialog({
  user,
  onClose,
}: {
  user: AdminUser | null;
  onClose: () => void;
}) {
  const t = useTranslations("resetUserPassword");
  const [submitting, setSubmitting] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [succeeded, setSucceeded] = useState(false);
  const name = user?.display_name ?? "";

  // Đóng là xóa trạng thái: mở cho người khác lần sau không được thấy lỗi hay thông báo cũ.
  function handleOpenChange(open: boolean) {
    if (!open) {
      setFailure(null);
      setSucceeded(false);
      onClose();
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user) {
      return;
    }
    const form = new FormData(event.currentTarget);
    const newPassword = String(form.get("newPassword"));
    // Kiểm ở client vì máy chủ không nhận ô nhập lại.
    if (newPassword !== String(form.get("confirmPassword"))) {
      setFailure("mismatch");
      return;
    }
    setSubmitting(true);
    setFailure(null);
    const result = await resetUserPassword(user.id, newPassword);
    setSubmitting(false);
    if (result === "ok") {
      setSucceeded(true);
      return;
    }
    setFailure(result);
  }

  return (
    <Dialog open={user !== null} onOpenChange={handleOpenChange}>
      {/* Tắt nút X có sẵn: nhãn của nó là chữ "Close" viết cứng, không dịch được. */}
      <DialogContent data-testid="reset-user-password-dialog" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
          <DialogDescription>{t("description", { name })}</DialogDescription>
        </DialogHeader>
        {succeeded ? (
          <>
            <p data-testid="reset-user-password-success" role="status">
              {t("success", { name })}
            </p>
            <DialogFooter>
              <DialogClose asChild>
                <Button>{t("close")}</Button>
              </DialogClose>
            </DialogFooter>
          </>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <label className="flex flex-col gap-1.5">
              <span>{t("newPassword")}</span>
              <Input
                data-testid="reset-user-password-new"
                name="newPassword"
                type="password"
                autoComplete="new-password"
                required
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span>{t("confirmPassword")}</span>
              <Input
                data-testid="reset-user-password-confirm"
                name="confirmPassword"
                type="password"
                autoComplete="new-password"
                required
              />
            </label>
            {failure ? (
              <p
                data-testid="reset-user-password-error"
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
              <Button data-testid="reset-user-password-submit" type="submit" disabled={submitting}>
                {submitting ? t("submitting") : t("submit")}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
