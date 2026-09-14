"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Ellipsis, KeyRound, Lock, LockOpen, UserCog, UserPlus } from "lucide-react";

import {
  ASSIGNABLE_ROLES,
  listUsers,
  updateUser,
  type AdminUser,
  type AssignableRole,
} from "@/app/lib/users-api";
import { CreateUserDialog } from "./create-user-dialog";
import { LockUserDialog } from "./lock-user-dialog";
import { useProfile } from "./profile-provider";
import { ResetUserPasswordDialog } from "./reset-user-password-dialog";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";

type State =
  | { kind: "loading" }
  | { kind: "forbidden" }
  | { kind: "error" }
  | { kind: "ready"; users: AdminUser[] };

const STATUS_CLASS = {
  active: "border-emerald-600/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  locked: "border-red-600/30 bg-red-500/10 text-red-700 dark:text-red-400",
};

export function UserAdmin() {
  const t = useTranslations("userAdmin");
  const tRole = useTranslations("roles");
  const profile = useProfile();
  const [state, setState] = useState<State>({ kind: "loading" });
  const [creating, setCreating] = useState(false);
  const [locking, setLocking] = useState<AdminUser | null>(null);
  const [resetting, setResetting] = useState<AdminUser | null>(null);
  const [actionFailed, setActionFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listUsers().then((result) => {
      if (!cancelled) {
        setState(result.kind === "ok" ? { kind: "ready", users: result.users } : result);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // Cập nhật bảng bằng dòng máy chủ trả về chứ không tự sửa tại chỗ: bảng luôn khớp thứ
  // máy chủ đã thật sự ghi.
  async function applyUpdate(
    user: AdminUser,
    patch: { role?: AssignableRole; is_locked?: boolean },
  ) {
    setActionFailed(false);
    const updated = await updateUser(user.id, patch);
    if (!updated) {
      setActionFailed(true);
      return;
    }
    setState((current) =>
      current.kind === "ready"
        ? {
            kind: "ready",
            users: current.users.map((candidate) =>
              candidate.id === updated.id ? updated : candidate,
            ),
          }
        : current,
    );
  }

  if (state.kind === "loading") {
    return (
      <p data-testid="user-admin-loading" className="opacity-70">
        {t("loading")}
      </p>
    );
  }
  if (state.kind === "forbidden") {
    return <p data-testid="user-admin-forbidden">{t("forbidden")}</p>;
  }
  if (state.kind === "error") {
    return (
      <p data-testid="user-admin-error" className="text-red-700 dark:text-red-400">
        {t("error")}
      </p>
    );
  }

  return (
    <div data-testid="user-admin">
      <div className="flex justify-end">
        <Button data-testid="user-admin-create" onClick={() => setCreating(true)}>
          <UserPlus />
          {t("create")}
        </Button>
      </div>
      {actionFailed ? (
        <p
          data-testid="user-admin-action-error"
          role="alert"
          className="mt-4 text-sm text-red-700 dark:text-red-400"
        >
          {t("actionFailed")}
        </p>
      ) : null}
      <Table data-testid="user-admin-table" className="mt-4">
        <TableHeader>
          <TableRow>
            <TableHead>{t("columns.name")}</TableHead>
            <TableHead>{t("columns.email")}</TableHead>
            <TableHead>{t("columns.role")}</TableHead>
            <TableHead>{t("columns.status")}</TableHead>
            <TableHead>
              <span className="sr-only">{t("actions")}</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {state.users.map((user) => {
            const isSelf = user.id === profile?.id;
            // Máy chủ từ chối mọi thao tác lên Super Admin và lên chính mình; ẩn hẳn menu
            // để không đưa ra lựa chọn chắc chắn thất bại.
            const manageable = user.role !== "super_admin" && !isSelf && profile !== null;
            const status = user.is_locked ? "locked" : "active";
            return (
              <TableRow key={user.id} data-testid="user-row">
                <TableCell className="font-medium">
                  {user.display_name}
                  {isSelf ? (
                    <span className="ml-1 font-normal text-muted-foreground">{t("you")}</span>
                  ) : null}
                </TableCell>
                <TableCell>{user.email}</TableCell>
                <TableCell data-testid="user-row-role">{tRole(user.role)}</TableCell>
                <TableCell>
                  <Badge
                    data-testid="user-row-status"
                    variant="outline"
                    className={STATUS_CLASS[status]}
                  >
                    {t(`status.${status}`)}
                  </Badge>
                </TableCell>
                <TableCell className="w-12 text-right">
                  {manageable ? (
                    <UserActions
                      user={user}
                      onChangeRole={(role) => applyUpdate(user, { role })}
                      onLock={() => setLocking(user)}
                      onUnlock={() => applyUpdate(user, { is_locked: false })}
                      onResetPassword={() => setResetting(user)}
                    />
                  ) : null}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      {/* Dialog nằm ngoài DropdownMenu: menu đóng lại khi chọn mục, dialog đặt bên trong
          sẽ bị tháo theo. */}
      <CreateUserDialog
        open={creating}
        onOpenChange={setCreating}
        onCreated={(user) =>
          setState((current) =>
            current.kind === "ready" ? { kind: "ready", users: [...current.users, user] } : current,
          )
        }
      />
      <LockUserDialog
        user={locking}
        onCancel={() => setLocking(null)}
        onConfirm={(user) => {
          setLocking(null);
          void applyUpdate(user, { is_locked: true });
        }}
      />
      <ResetUserPasswordDialog user={resetting} onClose={() => setResetting(null)} />
    </div>
  );
}

function UserActions({
  user,
  onChangeRole,
  onLock,
  onUnlock,
  onResetPassword,
}: {
  user: AdminUser;
  onChangeRole: (role: AssignableRole) => void;
  onLock: () => void;
  onUnlock: () => void;
  onResetPassword: () => void;
}) {
  const t = useTranslations("userAdmin");
  const tRole = useTranslations("roles");

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button data-testid="user-actions" variant="ghost" size="icon" aria-label={t("actions")}>
          <Ellipsis />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuSub>
          <DropdownMenuSubTrigger data-testid="user-action-role">
            <UserCog />
            {t("changeRole")}
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent>
            <DropdownMenuRadioGroup
              value={user.role}
              onValueChange={(value) => {
                if (value !== user.role) {
                  onChangeRole(value as AssignableRole);
                }
              }}
            >
              {ASSIGNABLE_ROLES.map((role) => (
                <DropdownMenuRadioItem key={role} value={role}>
                  {tRole(role)}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuSubContent>
        </DropdownMenuSub>
        {user.is_locked ? (
          <DropdownMenuItem data-testid="user-action-unlock" onSelect={onUnlock}>
            <LockOpen />
            {t("unlock")}
          </DropdownMenuItem>
        ) : (
          <DropdownMenuItem data-testid="user-action-lock" onSelect={onLock}>
            <Lock />
            {t("lock")}
          </DropdownMenuItem>
        )}
        <DropdownMenuItem data-testid="user-action-reset-password" onSelect={onResetPassword}>
          <KeyRound />
          {t("resetPassword")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
