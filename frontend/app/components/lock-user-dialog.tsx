"use client";

import { useTranslations } from "next-intl";

import type { AdminUser } from "@/app/lib/users-api";
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

// Khóa luôn qua bước xác nhận: bấm nhầm là người kia bị đá ra khỏi hệ thống trong vòng
// 15 phút. Mở khóa thì không cần, vì không làm mất gì của ai.
export function LockUserDialog({
  user,
  onCancel,
  onConfirm,
}: {
  user: AdminUser | null;
  onCancel: () => void;
  onConfirm: (user: AdminUser) => void;
}) {
  const t = useTranslations("lockUser");

  return (
    <Dialog
      open={user !== null}
      onOpenChange={(open) => {
        if (!open) {
          onCancel();
        }
      }}
    >
      {/* Tắt nút X có sẵn: nhãn của nó là chữ "Close" viết cứng, không dịch được. */}
      <DialogContent data-testid="lock-user-dialog" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
          <DialogDescription>
            {t("description", { name: user?.display_name ?? "" })}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline">
              {t("cancel")}
            </Button>
          </DialogClose>
          <Button
            data-testid="lock-user-confirm"
            variant="destructive"
            onClick={() => user && onConfirm(user)}
          >
            {t("confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
