"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { login, type LoginResult } from "@/app/lib/api";
import { safeNextPath } from "@/app/lib/next-path";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader } from "./ui/card";
import { Input } from "./ui/input";

export function LoginForm({ next }: { next: string | null }) {
  const t = useTranslations("login");
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [failure, setFailure] = useState<Exclude<LoginResult, "ok"> | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSubmitting(true);
    setFailure(null);
    const result = await login(String(form.get("email")), String(form.get("password")));
    if (result === "ok") {
      // replace chứ không push: nút quay lại không nên đưa người vừa đăng nhập về form.
      router.replace(safeNextPath(next));
      return;
    }
    setFailure(result);
    setSubmitting(false);
  }

  return (
    <Card className="mt-6">
      <CardHeader>
        <h1 className="text-lg font-semibold">{t("title")}</h1>
      </CardHeader>
      <CardContent>
        <form
          data-testid="login-form"
          onSubmit={handleSubmit}
          className="flex flex-col gap-4"
        >
          <label className="flex flex-col gap-1.5">
            <span>{t("email")}</span>
            <Input
              data-testid="login-email"
              name="email"
              type="email"
              autoComplete="username"
              required
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span>{t("password")}</span>
            <Input
              data-testid="login-password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
            />
          </label>
          {/* Một thông báo chung cho mọi kiểu sai: backend cố ý không cho biết email có
              tồn tại hay tài khoản bị khóa, giao diện không được nói nhiều hơn thế. */}
          {failure ? (
            <p
              data-testid="login-error"
              role="alert"
              className="text-sm text-red-700 dark:text-red-400"
            >
              {failure === "invalid" ? t("invalidCredentials") : t("unreachable")}
            </p>
          ) : null}
          <Button data-testid="login-submit" type="submit" disabled={submitting}>
            {submitting ? t("submitting") : t("submit")}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
