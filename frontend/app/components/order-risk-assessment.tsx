"use client";

import { useEffect, useRef, useState } from "react";
import { useFormatter, useTranslations } from "next-intl";

import { apiFetch } from "@/app/lib/api";
import { Badge } from "./ui/badge";
import { Field, Section } from "./order-detail";

// Phải đọc nguyên dạng tĩnh như thế này thì Next mới thay được giá trị lúc build.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

type RiskCause = {
  stage: string;
  seller_id: string | null;
  median_days: number;
  historical_median_days: number;
};

type RiskAssessment = {
  id: number;
  checkpoint: string;
  assessed_at: string;
  late_probability: number;
  is_high_risk: boolean;
  threshold_used: number;
  model_version: string;
  risk_cause: RiskCause;
  // Reconciliation (#33): null cho tới khi đơn được ghi nhận đã giao. Không đọc
  // needs_handling ở đây — thuộc phạm vi #35 (dựng nửa vời một khối "cần xử lý" chưa có
  // nút xử lý nào đi kèm thì vô nghĩa).
  was_correct: boolean | null;
};

type SellerRef = { seller_id: string; seller_city: string; seller_state: string };

// Cùng ba chặng của Timeline (order-detail.tsx) — mượn nguyên nhãn đã dịch ở đó thay vì
// dịch lại lần hai cho cùng một khái niệm.
const STAGE_LABEL_KEY: Record<string, string> = {
  payment_approval: "stages.paymentApproval",
  seller_handling: "stages.sellerHandling",
  carrier_transit: "stages.carrierTransit",
};

const RISK_LEVEL_CLASS: Record<"high" | "low", string> = {
  high: "border-red-600/30 bg-red-500/10 text-red-700 dark:text-red-400",
  low: "border-emerald-600/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
};

type Failure =
  | { kind: "missing_backend_url" }
  | { kind: "http_status"; status: number }
  // Lỗi mạng do trình duyệt sinh ra, luôn tiếng Anh và không dịch được; giữ nguyên văn.
  | { kind: "network"; detail: string };

class RiskAssessmentError extends Error {
  constructor(readonly failure: Failure) {
    super(failure.kind);
  }
}

type State =
  | { kind: "loading" }
  | { kind: "error"; failure: Failure }
  // Mảng rỗng: đơn Olist lịch sử, chưa từng có Risk Assessment nào. Mới nhất trên cùng,
  // đúng thứ tự máy chủ đã trả (list_risk_assessments, #33/#34).
  | { kind: "loaded"; history: RiskAssessment[] };

async function fetchAssessmentHistory(url: string): Promise<RiskAssessment[]> {
  if (!BACKEND_URL) {
    throw new RiskAssessmentError({ kind: "missing_backend_url" });
  }
  const response = await apiFetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new RiskAssessmentError({ kind: "http_status", status: response.status });
  }
  return (await response.json()) as RiskAssessment[];
}

export function OrderRiskAssessment({
  orderId,
  sellers,
  refreshToken,
}: {
  orderId: string;
  sellers: SellerRef[];
  // Tăng ở order-detail.tsx sau mỗi thao tác mốc/sửa mốc thành công, để buộc tải lại đúng
  // url này (ghi nhận mốc mới sinh thêm một dòng; giao hàng đối chiếu lại mọi dòng cũ).
  refreshToken?: number;
}) {
  const t = useTranslations("orderDetail");
  const tOrders = useTranslations("orders");
  const [state, setState] = useState<State>({ kind: "loading" });
  // true khi lần gọi lại (refreshToken > 0) không tải được — đọc riêng, không lẫn với
  // state.kind vì lịch sử cũ vẫn đang hiện đúng, chỉ chưa chắc là bản mới nhất.
  const [historyRefreshFailed, setHistoryRefreshFailed] = useState(false);
  const url = `${BACKEND_URL}/orders/${encodeURIComponent(orderId)}/risk-assessments`;
  const requestKey = `${url}#${refreshToken ?? 0}`;

  // Cùng chốt với order-detail.tsx: Strict Mode không gọi hai lần, và phản hồi của đơn cũ
  // không đè lên đơn mới.
  const requested = useRef<string | null>(null);

  useEffect(() => {
    if (requested.current === requestKey) {
      return;
    }
    requested.current = requestKey;
    setHistoryRefreshFailed(false);

    fetchAssessmentHistory(url)
      .then((history) => {
        if (requested.current === requestKey) {
          setState({ kind: "loaded", history });
        }
      })
      .catch((error: unknown) => {
        if (requested.current !== requestKey) {
          return;
        }
        // Lần gọi lại sau một thao tác đã thành công: giữ nguyên lịch sử đang hiện thay vì
        // thay bằng màn hình lỗi — thao tác gốc không hề thất bại. Vẫn báo riêng (khác với
        // order-detail.tsx tải hỏng, vốn đã có banner của chính nó) để không im lặng bỏ qua
        // một lần tải lại thật sự thất bại.
        if ((refreshToken ?? 0) > 0) {
          setHistoryRefreshFailed(true);
          return;
        }
        setState({
          kind: "error",
          failure:
            error instanceof RiskAssessmentError
              ? error.failure
              : {
                  kind: "network",
                  detail: error instanceof Error ? error.message : String(error),
                },
        });
      });
  }, [requestKey, url, refreshToken]);

  function failureDetail(failure: Failure): string {
    return failure.kind === "missing_backend_url"
      ? tOrders("errorDetail.missingBackendUrl")
      : failure.kind === "http_status"
        ? tOrders("errorDetail.httpStatus", { status: failure.status })
        : failure.detail;
  }

  return (
    <Section title={t("riskAssessment.title")} testId="order-risk-assessment">
      {historyRefreshFailed ? (
        <p
          data-testid="risk-assessment-refresh-failed"
          className="mb-3 text-sm text-amber-700 dark:text-amber-400"
        >
          {t("riskAssessment.refreshFailed")}
        </p>
      ) : null}
      {state.kind === "loading" ? (
        <p data-testid="risk-assessment-loading" className="opacity-70">
          {t("riskAssessment.loading")}
        </p>
      ) : state.kind === "error" ? (
        <p data-testid="risk-assessment-error" className="text-red-700 dark:text-red-400">
          {t("riskAssessment.error", { detail: failureDetail(state.failure) })}
        </p>
      ) : state.history.length === 0 ? (
        <p data-testid="risk-assessment-empty" className="text-muted-foreground">
          {t("riskAssessment.empty")}
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          <AssessmentDetails assessment={state.history[0]} sellers={sellers} />
          {state.history.length > 1 ? (
            <div className="flex flex-col gap-3 border-t pt-4">
              <h3 className="text-sm font-medium">{t("riskAssessment.history.title")}</h3>
              <ul className="flex flex-col gap-3">
                {state.history.slice(1).map((assessment) => (
                  <li key={assessment.id} data-testid="risk-assessment-history-row">
                    <HistoryRow assessment={assessment} />
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      )}
    </Section>
  );
}

// Cờ đúng/sai đối chiếu (#33): null tới khi đơn được ghi nhận đã giao, nên không hiện gì
// trước đó — không phải một trạng thái thứ ba cần vẽ riêng.
function OutcomeBadge({ wasCorrect, testId }: { wasCorrect: boolean | null; testId: string }) {
  const t = useTranslations("orderDetail");
  if (wasCorrect === null) {
    return null;
  }
  return (
    <Badge
      data-testid={testId}
      variant="outline"
      className={
        wasCorrect
          ? "border-emerald-600/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
          : "border-red-600/30 bg-red-500/10 text-red-700 dark:text-red-400"
      }
    >
      {t(wasCorrect ? "riskAssessment.outcome.correct" : "riskAssessment.outcome.incorrect")}
    </Badge>
  );
}

// Dòng lịch sử nhạt hơn dòng nổi bật: chỉ probability/badge/checkpoint/assessedAt/outcome,
// không có nguyên nhân chi tiết (stage/seller) — đỡ rối khi một đơn có nhiều lần đánh giá.
function HistoryRow({ assessment }: { assessment: RiskAssessment }) {
  const t = useTranslations("orderDetail");
  const format = useFormatter();
  const level = assessment.is_high_risk ? "high" : "low";
  // Cùng lý do với AssessmentDetails: assessed_at là mốc thật có offset, tính múi giờ
  // trình duyệt chỉ sau khi đã có dữ liệu để không lệch khi hydrate.
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
      <Badge
        data-testid="risk-assessment-history-badge"
        variant="outline"
        className={RISK_LEVEL_CLASS[level]}
      >
        {t(`riskAssessment.level.${level}`)}
      </Badge>
      <span data-testid="risk-assessment-history-probability">
        {format.number(assessment.late_probability, "percent")}
      </span>
      <span data-testid="risk-assessment-history-checkpoint">
        {t(`riskAssessment.checkpointValues.${assessment.checkpoint}`)}
      </span>
      <span data-testid="risk-assessment-history-assessed-at">
        {format.dateTime(new Date(assessment.assessed_at), "localDateTime", { timeZone })}
      </span>
      <OutcomeBadge
        wasCorrect={assessment.was_correct}
        testId="risk-assessment-history-outcome"
      />
    </div>
  );
}

function AssessmentDetails({
  assessment,
  sellers,
}: {
  assessment: RiskAssessment;
  sellers: SellerRef[];
}) {
  const t = useTranslations("orderDetail");
  const format = useFormatter();
  const level = assessment.is_high_risk ? "high" : "low";
  const seller = assessment.risk_cause.seller_id
    ? (sellers.find((candidate) => candidate.seller_id === assessment.risk_cause.seller_id) ??
      null)
    : null;

  // assessed_at là mốc thật có offset ("...+00:00"), không phải dấu thời gian không múi
  // giờ của dữ liệu Olist — cùng quy ước với order-notes.tsx, khác utcTimestamp mà
  // Timeline dùng cho các mốc của đơn. Chỉ tính múi giờ trình duyệt ở đây, sau khi đã có
  // dữ liệu (không nằm trong HTML dựng từ máy chủ), nên không có gì để lệch khi hydrate.
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  return (
    <dl className="flex flex-col gap-2">
      <Field label={t("riskAssessment.lateProbability")} testId="risk-assessment-probability">
        {format.number(assessment.late_probability, "percent")}
      </Field>
      <Field label={t("riskAssessment.title")} testId="risk-assessment-level">
        <Badge data-testid="risk-assessment-badge" variant="outline" className={RISK_LEVEL_CLASS[level]}>
          {t(`riskAssessment.level.${level}`)}
        </Badge>
      </Field>
      {assessment.is_high_risk ? (
        <>
          <Field
            label={t(STAGE_LABEL_KEY[assessment.risk_cause.stage])}
            testId="risk-assessment-stage"
          >
            {t("riskAssessment.cause.expectedVsTypical", {
              expected: format.number(assessment.risk_cause.median_days, "days"),
              typical: format.number(assessment.risk_cause.historical_median_days, "days"),
            })}
          </Field>
          {seller ? (
            <Field
              label={t("riskAssessment.cause.sellerCaused")}
              testId="risk-assessment-seller"
            >
              <span className="font-mono break-all">{seller.seller_id}</span>
              <span className="text-muted-foreground">
                {" "}
                · {seller.seller_city} · {seller.seller_state}
              </span>
            </Field>
          ) : null}
        </>
      ) : null}
      <Field label={t("riskAssessment.checkpoint")} testId="risk-assessment-checkpoint">
        {t(`riskAssessment.checkpointValues.${assessment.checkpoint}`)}
      </Field>
      <Field label={t("riskAssessment.assessedAt")} testId="risk-assessment-assessed-at">
        {format.dateTime(new Date(assessment.assessed_at), "localDateTime", { timeZone })}
      </Field>
      {assessment.was_correct !== null ? (
        <Field label={t("riskAssessment.outcome.title")} testId="risk-assessment-outcome-field">
          <OutcomeBadge wasCorrect={assessment.was_correct} testId="risk-assessment-outcome" />
        </Field>
      ) : null}
    </dl>
  );
}
