"use client";

import { useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";

import {
  createUser,
  manageableRoles,
  type AdminUser,
  type AssignableRole,
  type CreateUserFailure,
} from "@/app/lib/users-api";
import { useProfile } from "./profile-provider";
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

export function CreateUserDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (user: AdminUser) => void;
}) {
  const t = useTranslations("createUser");
  const tRole = useTranslations("roles");
  // Chỉ đưa ra vai trò người đăng nhập được phép cấp; máy chủ vẫn tự kiểm.
  const roles = manageableRoles(useProfile()?.role);
  const [role, setRole] = useState<AssignableRole>("operations_staff");
  const [submitting, setSubmitting] = useState(false);
  const [failure, setFailure] = useState<CreateUserFailure | null>(null);

  // Đóng là xóa trạng thái: mở lại lần sau không được thấy lỗi hay vai trò của lần trước.
  // Các ô nhập tự trống vì DialogContent bị tháo khi đóng.
  function handleOpenChange(next: boolean) {
    if (!next) {
      setRole("operations_staff");
      setFailure(null);
    }
    onOpenChange(next);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSubmitting(true);
    setFailure(null);
    const result = await createUser({
      display_name: String(form.get("displayName")),
      email: String(form.get("email")),
      role,
      password: String(form.get("password")),
    });
    setSubmitting(false);
    if (result.kind === "ok") {
      onCreated(result.user);
      handleOpenChange(false);
      return;
    }
    setFailure(result.kind);
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      {/* Tắt nút X có sẵn: nhãn của nó là chữ "Close" viết cứng, không dịch được. */}
      <DialogContent data-testid="create-user-dialog" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
          <DialogDescription>{t("description")}</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1.5">
            <span>{t("displayName")}</span>
            <Input data-testid="create-user-name" name="displayName" autoComplete="off" required />
          </label>
          <label className="flex flex-col gap-1.5">
            <span>{t("email")}</span>
            <Input
              data-testid="create-user-email"
              name="email"
              type="email"
              autoComplete="off"
              required
            />
          </label>
          <div className="flex flex-col gap-1.5">
            <span id="create-user-role-label">{t("role")}</span>
            <Select value={role} onValueChange={(value) => setRole(value as AssignableRole)}>
              <SelectTrigger
                data-testid="create-user-role"
                aria-labelledby="create-user-role-label"
                className="w-full"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {roles.map((value) => (
                  <SelectItem key={value} value={value}>
                    {tRole(value)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <label className="flex flex-col gap-1.5">
            <span>{t("password")}</span>
            <Input
              data-testid="create-user-password"
              name="password"
              type="password"
              autoComplete="new-password"
              required
            />
          </label>
          {failure ? (
            <p
              data-testid="create-user-error"
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
            <Button data-testid="create-user-submit" type="submit" disabled={submitting}>
              {submitting ? t("submitting") : t("submit")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
