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
  checkpoint: string;
  assessed_at: string;
  late_probability: number;
  is_high_risk: boolean;
  risk_cause: RiskCause;
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
  // null: đơn Olist lịch sử, chưa từng có Risk Assessment nào (mảng rỗng từ máy chủ).
  | { kind: "loaded"; assessment: RiskAssessment | null };

// needs_handling/was_correct của RiskAssessmentOut chỉ có ý nghĩa thật ở chính endpoint
// này; khối này chỉ đọc từ đây, không đọc lại dữ liệu đánh giá trả về lúc tạo đơn hay ghi
// mốc — nơi hai trường đó luôn mặc định.
async function fetchLatestAssessment(url: string): Promise<RiskAssessment | null> {
  if (!BACKEND_URL) {
    throw new RiskAssessmentError({ kind: "missing_backend_url" });
  }
  const response = await apiFetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new RiskAssessmentError({ kind: "http_status", status: response.status });
  }
  const data = (await response.json()) as RiskAssessment[];
  return data[0] ?? null;
}

export function OrderRiskAssessment({
  orderId,
  sellers,
}: {
  orderId: string;
  sellers: SellerRef[];
}) {
  const t = useTranslations("orderDetail");
  const tOrders = useTranslations("orders");
  const [state, setState] = useState<State>({ kind: "loading" });
  const url = `${BACKEND_URL}/orders/${encodeURIComponent(orderId)}/risk-assessments`;

  // Cùng chốt với order-detail.tsx: Strict Mode không gọi hai lần, và phản hồi của đơn cũ
  // không đè lên đơn mới.
  const requested = useRef<string | null>(null);

  useEffect(() => {
    if (requested.current === url) {
      return;
    }
    requested.current = url;

    fetchLatestAssessment(url)
      .then((assessment) => {
        if (requested.current === url) {
          setState({ kind: "loaded", assessment });
        }
      })
      .catch((error: unknown) => {
        if (requested.current !== url) {
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
  }, [url]);

  function failureDetail(failure: Failure): string {
    return failure.kind === "missing_backend_url"
      ? tOrders("errorDetail.missingBackendUrl")
      : failure.kind === "http_status"
        ? tOrders("errorDetail.httpStatus", { status: failure.status })
        : failure.detail;
  }

  return (
    <Section title={t("riskAssessment.title")} testId="order-risk-assessment">
      {state.kind === "loading" ? (
        <p data-testid="risk-assessment-loading" className="opacity-70">
          {t("riskAssessment.loading")}
        </p>
      ) : state.kind === "error" ? (
        <p data-testid="risk-assessment-error" className="text-red-700 dark:text-red-400">
          {t("riskAssessment.error", { detail: failureDetail(state.failure) })}
        </p>
      ) : state.assessment === null ? (
        <p data-testid="risk-assessment-empty" className="text-muted-foreground">
          {t("riskAssessment.empty")}
        </p>
      ) : (
        <AssessmentDetails assessment={state.assessment} sellers={sellers} />
      )}
    </Section>
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
    </dl>
  );
}
