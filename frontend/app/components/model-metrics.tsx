"use client";

import { useEffect, useRef, useState } from "react";
import { useFormatter, useTranslations } from "next-intl";

import { apiFetch } from "@/app/lib/api";
import { Badge } from "./ui/badge";
import { Field, Section } from "./order-detail";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";

// Phải đọc nguyên dạng tĩnh như thế này thì Next mới thay được giá trị lúc build.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

// Cùng ba mốc dự đoán của Timeline/OrderRiskAssessment — thứ tự cố định để bảng luôn hiện
// theo đúng trình tự vòng đời, không phụ thuộc thứ tự khoá trong JSON trả về.
const CHECKPOINTS = ["order_placed", "payment_approved", "handed_to_carrier"] as const;
type Checkpoint = (typeof CHECKPOINTS)[number];

type CheckpointMetrics = { precision: number; recall: number; f1: number };

type AlgorithmReport = Record<Checkpoint, CheckpointMetrics>;

type TrainingReport = {
  model_version: string;
  trained_at: string;
  selected_algorithm: string;
  f1_target: number;
  f1_at_order_placed: number;
  meets_f1_target: boolean;
  algorithms: Record<string, AlgorithmReport>;
};

type ReconciliationCheckpoint = {
  checkpoint: Checkpoint;
  total: number;
  correct: number;
  incorrect: number;
  precision: number | null;
  recall: number | null;
  small_sample: boolean;
};

type ModelMetricsData = {
  trained: boolean;
  report: TrainingReport | null;
  risk_threshold: number;
  reconciliation: ReconciliationCheckpoint[];
};

type Failure =
  | { kind: "missing_backend_url" }
  | { kind: "http_status"; status: number }
  // Lỗi mạng do trình duyệt sinh ra, luôn tiếng Anh và không dịch được; giữ nguyên văn.
  | { kind: "network"; detail: string };

class ModelMetricsError extends Error {
  constructor(readonly failure: Failure) {
    super(failure.kind);
  }
}

type State =
  | { kind: "loading" }
  | { kind: "error"; failure: Failure }
  | { kind: "loaded"; data: ModelMetricsData };

const STATUS_CLASS: Record<"met" | "notMet", string> = {
  met: "border-emerald-600/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  notMet: "border-red-600/30 bg-red-500/10 text-red-700 dark:text-red-400",
};

async function fetchModelMetrics(url: string): Promise<ModelMetricsData> {
  if (!BACKEND_URL) {
    throw new ModelMetricsError({ kind: "missing_backend_url" });
  }
  const response = await apiFetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new ModelMetricsError({ kind: "http_status", status: response.status });
  }
  return (await response.json()) as ModelMetricsData;
}

export function ModelMetrics() {
  const t = useTranslations("modelMetrics");
  const tOrderDetail = useTranslations("orderDetail");
  const format = useFormatter();
  const url = `${BACKEND_URL}/model-metrics`;
  const [state, setState] = useState<State>({ kind: "loading" });

  // Cùng chốt chống gọi kép của Strict Mode với dashboard.tsx/order-risk-assessment.tsx.
  const requested = useRef<string | null>(null);

  useEffect(() => {
    if (requested.current === url) {
      return;
    }
    requested.current = url;

    fetchModelMetrics(url)
      .then((data) => {
        if (requested.current === url) {
          setState({ kind: "loaded", data });
        }
      })
      .catch((error: unknown) => {
        if (requested.current !== url) {
          return;
        }
        setState({
          kind: "error",
          failure:
            error instanceof ModelMetricsError
              ? error.failure
              : { kind: "network", detail: error instanceof Error ? error.message : String(error) },
        });
      });
  }, [url]);

  function checkpointLabel(checkpoint: Checkpoint): string {
    return tOrderDetail(`riskAssessment.checkpointValues.${checkpoint}`);
  }

  if (state.kind === "loading") {
    return (
      <p data-testid="model-metrics-loading" className="opacity-70">
        {t("loading")}
      </p>
    );
  }

  if (state.kind === "error") {
    const { failure } = state;
    const detail =
      failure.kind === "missing_backend_url"
        ? t("errorDetail.missingBackendUrl")
        : failure.kind === "http_status"
          ? t("errorDetail.httpStatus", { status: failure.status })
          : failure.detail;
    return (
      <p data-testid="model-metrics-error" className="text-red-700 dark:text-red-400">
        {t("error", { detail })}
      </p>
    );
  }

  const { data } = state;

  return (
    <div className="flex flex-col gap-6">
      <Section title={t("title")} testId="model-metrics-overview">
        <div className="flex flex-col gap-4">
          {!data.trained ? (
            <p data-testid="model-metrics-not-trained" className="text-muted-foreground">
              {t("notTrained")}
            </p>
          ) : null}
          <dl className="flex flex-col gap-2">
            {data.report ? (
              <>
                <Field label={t("modelVersion")} testId="model-metrics-model-version">
                  {data.report.model_version}
                </Field>
                <Field label={t("selectedAlgorithm")} testId="model-metrics-selected-algorithm">
                  {data.report.selected_algorithm}
                </Field>
                <Field label={t("f1AtOrderPlaced")} testId="model-metrics-f1-status">
                  {format.number(data.report.f1_at_order_placed, "percent")}
                  {" · "}
                  {t("f1Target", { target: format.number(data.report.f1_target, "percent") })}
                  {" · "}
                  <Badge
                    variant="outline"
                    className={STATUS_CLASS[data.report.meets_f1_target ? "met" : "notMet"]}
                  >
                    {t(data.report.meets_f1_target ? "f1Status.met" : "f1Status.notMet")}
                  </Badge>
                </Field>
              </>
            ) : null}
            <Field label={t("threshold")} testId="model-metrics-threshold">
              {format.number(data.risk_threshold, "percent")}
            </Field>
          </dl>
        </div>
      </Section>

      {data.report ? (
        <Section title={t("algorithmComparison.title")} testId="model-metrics-algorithm-comparison">
          <Table data-testid="model-metrics-algorithm-table">
            <TableHeader>
              <TableRow>
                <TableHead>{t("algorithmComparison.algorithm")}</TableHead>
                {CHECKPOINTS.map((checkpoint) => (
                  <TableHead key={checkpoint}>{checkpointLabel(checkpoint)}</TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {Object.entries(data.report.algorithms).map(([algorithm, scores]) => (
                <TableRow key={algorithm} data-testid="model-metrics-algorithm-row">
                  <TableCell>
                    {algorithm}
                    {algorithm === data.report!.selected_algorithm ? (
                      <Badge variant="outline" className="ml-2">
                        {t("algorithmComparison.selectedBadge")}
                      </Badge>
                    ) : null}
                  </TableCell>
                  {CHECKPOINTS.map((checkpoint) => {
                    const cell = scores[checkpoint];
                    return (
                      <TableCell key={checkpoint}>
                        {t("metric.f1")} {format.number(cell.f1, "percent")}
                        <br />
                        {t("metric.precision")} {format.number(cell.precision, "percent")}
                        {" · "}
                        {t("metric.recall")} {format.number(cell.recall, "percent")}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Section>
      ) : null}

      <Section title={t("reconciliation.title")} testId="model-metrics-reconciliation">
        <Table data-testid="reconciliation-table">
          <TableHeader>
            <TableRow>
              <TableHead>{tOrderDetail("riskAssessment.checkpoint")}</TableHead>
              <TableHead>{t("reconciliation.total")}</TableHead>
              <TableHead>{t("reconciliation.correct")}</TableHead>
              <TableHead>{t("reconciliation.incorrect")}</TableHead>
              <TableHead>{t("metric.precision")}</TableHead>
              <TableHead>{t("metric.recall")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.reconciliation.map((row) => (
              <TableRow key={row.checkpoint} data-testid="reconciliation-row">
                <TableCell>{checkpointLabel(row.checkpoint)}</TableCell>
                <TableCell>
                  <span data-testid="reconciliation-total">{row.total}</span>
                  {row.small_sample ? (
                    <p
                      data-testid="reconciliation-small-sample"
                      role="status"
                      className="mt-1 rounded-md border border-amber-500/40 bg-amber-500/10 px-2 py-1 text-xs text-amber-900 dark:text-amber-200"
                    >
                      {t("reconciliation.smallSampleWarning", { count: row.total })}
                    </p>
                  ) : null}
                </TableCell>
                <TableCell>{row.correct}</TableCell>
                <TableCell>{row.incorrect}</TableCell>
                <TableCell>
                  {row.precision === null ? "—" : format.number(row.precision, "percent")}
                </TableCell>
                <TableCell>
                  {row.recall === null ? "—" : format.number(row.recall, "percent")}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Section>
    </div>
  );
}
