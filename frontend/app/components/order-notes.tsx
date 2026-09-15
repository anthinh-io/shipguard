"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useFormatter, useTranslations } from "next-intl";

import { apiFetch } from "@/app/lib/api";
import type { Role } from "@/app/lib/users-api";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Textarea } from "./ui/textarea";

// Phải đọc nguyên dạng tĩnh như thế này thì Next mới thay được giá trị lúc build.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

// Cùng giới hạn với backend (1–2.000 ký tự sau khi cắt khoảng trắng).
const MAX_NOTE_LENGTH = 2000;

type OrderNote = {
  id: number;
  body: string;
  created_at: string;
  author: { display_name: string; role: Role };
};

type Failure =
  | { kind: "missing_backend_url" }
  | { kind: "http_status"; status: number }
  // Lỗi mạng do trình duyệt sinh ra, luôn tiếng Anh và không dịch được; giữ nguyên văn.
  | { kind: "network"; detail: string };

class OrderNotesError extends Error {
  constructor(readonly failure: Failure) {
    super(failure.kind);
  }
}

function toFailure(error: unknown): Failure {
  return error instanceof OrderNotesError
    ? error.failure
    : { kind: "network", detail: error instanceof Error ? error.message : String(error) };
}

type State =
  | { kind: "loading" }
  | { kind: "error"; failure: Failure }
  | { kind: "loaded"; notes: OrderNote[] };

type Problem =
  | { kind: "blank" }
  | { kind: "tooLong"; length: number }
  // Máy chủ trả 422: nội dung lọt qua kiểm ở trình duyệt (trim() của JS và strip() của
  // Python không cắt cùng một tập ký tự) nhưng vẫn ngoài 1–2.000 ký tự.
  | { kind: "rejected" }
  | { kind: "submit"; failure: Failure };

async function requestNotes(url: string, init?: RequestInit): Promise<Response> {
  if (!BACKEND_URL) {
    throw new OrderNotesError({ kind: "missing_backend_url" });
  }
  const response = await apiFetch(url, { cache: "no-store", ...init });
  if (!response.ok) {
    throw new OrderNotesError({ kind: "http_status", status: response.status });
  }
  return response;
}

export function OrderNotes({ orderId }: { orderId: string }) {
  const t = useTranslations("orderNotes");
  const tOrders = useTranslations("orders");
  const [state, setState] = useState<State>({ kind: "loading" });
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const url = `${BACKEND_URL}/orders/${encodeURIComponent(orderId)}/notes`;

  // Cùng chốt với order-detail.tsx: Strict Mode không gọi hai lần, và phản hồi của đơn cũ
  // không đè lên đơn mới.
  const requested = useRef<string | null>(null);

  useEffect(() => {
    if (requested.current === url) {
      return;
    }
    requested.current = url;

    requestNotes(url)
      .then((response) => response.json() as Promise<OrderNote[]>)
      .then((notes) => {
        if (requested.current === url) {
          setState({ kind: "loaded", notes });
        }
      })
      .catch((error: unknown) => {
        if (requested.current === url) {
          setState({ kind: "error", failure: toFailure(error) });
        }
      });
  }, [url]);

  function failureDetail(failure: Failure): string {
    return failure.kind === "missing_backend_url"
      ? tOrders("errorDetail.missingBackendUrl")
      : failure.kind === "http_status"
        ? tOrders("errorDetail.httpStatus", { status: failure.status })
        : failure.detail;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // Đếm theo ký tự Unicode như backend, không theo đơn vị UTF-16 của .length — một emoji
    // là một ký tự chứ không phải hai.
    const length = Array.from(body.trim()).length;
    if (length === 0) {
      setProblem({ kind: "blank" });
      return;
    }
    if (length > MAX_NOTE_LENGTH) {
      setProblem({ kind: "tooLong", length });
      return;
    }
    setSubmitting(true);
    setProblem(null);
    try {
      const response = await requestNotes(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body }),
      });
      const note = (await response.json()) as OrderNote;
      setState((current) =>
        current.kind === "loaded" ? { kind: "loaded", notes: [note, ...current.notes] } : current,
      );
      setBody("");
    } catch (error) {
      const failure = toFailure(error);
      setProblem(
        failure.kind === "http_status" && failure.status === 422
          ? { kind: "rejected" }
          : { kind: "submit", failure },
      );
    } finally {
      setSubmitting(false);
    }
  }

  const problemMessage =
    problem === null
      ? null
      : problem.kind === "blank"
        ? t("blank")
        : problem.kind === "tooLong"
          ? t("tooLong", { length: problem.length })
          : problem.kind === "rejected"
            ? t("rejected")
            : t("submitError", { detail: failureDetail(problem.failure) });

  return (
    <Card data-testid="order-notes">
      <CardHeader>
        <CardTitle>{t("title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {state.kind === "loading" ? (
          <p data-testid="order-notes-loading" className="opacity-70">
            {t("loading")}
          </p>
        ) : state.kind === "error" ? (
          <p data-testid="order-notes-load-error" className="text-red-700 dark:text-red-400">
            {t("loadError", { detail: failureDetail(state.failure) })}
          </p>
        ) : (
          <>
            {/* Chỉ cho thêm khi đã thấy danh sách: ghi chú mới phải nằm trên cùng những gì
                người viết vừa đọc. */}
            <form onSubmit={handleSubmit} className="flex flex-col gap-2" noValidate>
              <Textarea
                data-testid="order-notes-input"
                aria-label={t("title")}
                placeholder={t("placeholder")}
                value={body}
                onChange={(event) => setBody(event.target.value)}
                aria-invalid={problem !== null && problem.kind !== "submit"}
                className="max-h-64"
              />
              {problemMessage ? (
                <p
                  data-testid="order-notes-error"
                  role="alert"
                  className="text-sm text-red-700 dark:text-red-400"
                >
                  {problemMessage}
                </p>
              ) : null}
              <p className="text-xs text-muted-foreground">{t("appendOnlyHint")}</p>
              <Button
                data-testid="order-notes-submit"
                type="submit"
                size="sm"
                className="self-end"
                disabled={submitting}
              >
                {submitting ? t("submitting") : t("submit")}
              </Button>
            </form>
            <NoteList notes={state.notes} />
          </>
        )}
      </CardContent>
    </Card>
  );
}

function NoteList({ notes }: { notes: OrderNote[] }) {
  const t = useTranslations("orderNotes");
  const tRole = useTranslations("roles");
  const format = useFormatter();

  if (notes.length === 0) {
    return (
      <p data-testid="order-notes-empty" className="text-muted-foreground">
        {t("empty")}
      </p>
    );
  }

  // created_at là mốc thật kèm múi giờ ("…+00:00"), nên đưa thẳng vào new Date() — không
  // qua utcTimestamp, vốn dành cho dấu thời gian không múi giờ của dữ liệu Olist. Múi giờ
  // trình duyệt truyền tường minh: next-intl mặc định dùng múi giờ của máy chủ. Chỉ đọc ở
  // đây, sau khi đã gọi xong máy chủ, nên không có mốc giờ nào trong HTML dựng từ máy chủ
  // để lệch khi hydrate.
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  return (
    <ul className="flex flex-col divide-y">
      {notes.map((note) => (
        <li key={note.id} data-testid="order-note" className="min-w-0 py-3 first:pt-0 last:pb-0">
          <p data-testid="order-note-body" className="break-words whitespace-pre-wrap">
            {note.body}
          </p>
          <p data-testid="order-note-byline" className="mt-1 text-sm text-muted-foreground">
            {t("byline", {
              name: note.author.display_name,
              role: tRole(note.author.role),
              time: format.dateTime(new Date(note.created_at), "localDateTime", { timeZone }),
            })}
          </p>
        </li>
      ))}
    </ul>
  );
}
