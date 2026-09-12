"use client";

import { useEffect, useRef, useState } from "react";
import { useFormatter, useTranslations } from "next-intl";

import { KpiTile } from "./kpi-tile";

// Phải đọc nguyên dạng tĩnh như thế này thì Next mới thay được giá trị lúc build.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

type ReportingPeriod = {
  start_date: string;
  end_date: string;
};

type StageDuration = {
  median_days: number | null;
  p90_days: number | null;
};

type Kpis = {
  delivered_orders: number;
  late_orders: number;
  on_time_rate: number | null;
  payment_approval: StageDuration;
  seller_handling: StageDuration;
  carrier_transit: StageDuration;
  late_related_low_review_rate: number | null;
};

type DashboardData = {
  reporting_period: ReportingPeriod | null;
  kpis: Kpis;
};

type Failure =
  | { kind: "missing_backend_url" }
  | { kind: "http_status"; status: number }
  // Lỗi mạng do trình duyệt sinh ra, luôn tiếng Anh và không dịch được; giữ nguyên văn.
  | { kind: "network"; detail: string };

class DashboardError extends Error {
  constructor(readonly failure: Failure) {
    super(failure.kind);
  }
}

type State =
  | { kind: "loading" }
  | { kind: "error"; failure: Failure }
  | { kind: "loaded"; data: DashboardData };

async function fetchDashboard(url: string): Promise<DashboardData> {
  // Ném thay vì dựng trạng thái lỗi thẳng trong effect: cả hai hiện ra cùng một chỗ,
  // nhưng ném thì đi qua nhánh catch chung và không gọi setState đồng bộ trong effect.
  if (!BACKEND_URL) {
    throw new DashboardError({ kind: "missing_backend_url" });
  }
  const response = await fetch(url, { cache: "no-store" });
  // Phản hồi lỗi của FastAPI vẫn là JSON hợp lệ — 422 khi ngày sai định dạng chẳng
  // hạn — nên phải chặn theo mã trạng thái, không thể chỉ dựa vào json() ném hay không.
  if (!response.ok) {
    throw new DashboardError({ kind: "http_status", status: response.status });
  }
  return (await response.json()) as DashboardData;
}

export default function Dashboard() {
  const t = useTranslations("dashboard");
  const format = useFormatter();
  const [state, setState] = useState<State>({ kind: "loading" });
  const url = `${BACKEND_URL}/dashboard`;
  // Strict Mode gọi effect mount hai lần ở chế độ phát triển và không có lớp nào gộp
  // fetch trần, nên không chặn thì mỗi lần mở trang sinh hai lần gọi máy chủ.
  // AbortController không thay thế được chốt này: request đã huỷ vẫn là một request.
  //
  // Chốt nhớ *địa chỉ đã gọi* chứ không phải "đã gọi lần nào chưa". Hôm nay địa chỉ cố
  // định nên hai cách chạy y hệt, nhưng khi bộ lọc gắn vào chuỗi truy vấn thì đổi bộ
  // lọc vẫn gọi lại được, còn một cờ boolean sẽ chặn vĩnh viễn.
  const requested = useRef<string | null>(null);

  useEffect(() => {
    if (requested.current === url) {
      return;
    }
    requested.current = url;

    fetchDashboard(url)
      .then((data) => setState({ kind: "loaded", data }))
      .catch((error: unknown) =>
        setState({
          kind: "error",
          failure:
            error instanceof DashboardError
              ? error.failure
              : {
                  kind: "network",
                  detail: error instanceof Error ? error.message : String(error),
                },
        }),
      );
  }, [url]);

  if (state.kind === "loading") {
    return (
      <p data-testid="dashboard-loading" className="opacity-70">
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
      <p data-testid="dashboard-error" className="text-red-700 dark:text-red-400">
        {t("error", { detail })}
      </p>
    );
  }

  const { reporting_period, kpis } = state.data;
  const period = reporting_period
    ? `${format.dateTime(new Date(reporting_period.start_date), "fullDate")} – ${format.dateTime(
        new Date(reporting_period.end_date),
        "fullDate",
      )}`
    : t("noDeliveredOrders");

  return (
    <>
      <p data-testid="reporting-period" className="mt-1 opacity-70">
        {t("reportingPeriod", { period })}
      </p>
      <section
        data-testid="kpi-grid"
        className="mt-6 grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-4"
      >
        <KpiTile
          testId="kpi-on-time-rate"
          label={t("onTimeRate")}
          // Kỳ lọc có thể không ra đơn nào; lúc đó tỷ lệ là rỗng chứ không phải 0%.
          value={
            kpis.on_time_rate === null
              ? "—"
              : format.number(kpis.on_time_rate, "percent")
          }
          hint={t("deliveredOrders", { count: kpis.delivered_orders })}
        />
        <KpiTile
          testId="kpi-late-orders"
          label={t("lateOrders")}
          value={format.number(kpis.late_orders)}
        />
        <StageTile
          testId="kpi-payment-approval"
          label={t("paymentApproval")}
          stage={kpis.payment_approval}
        />
        <StageTile
          testId="kpi-seller-handling"
          label={t("sellerHandling")}
          stage={kpis.seller_handling}
        />
        <StageTile
          testId="kpi-carrier-transit"
          label={t("carrierTransit")}
          stage={kpis.carrier_transit}
        />
        <KpiTile
          testId="kpi-late-related-low-review-rate"
          label={t("lateRelatedLowReviewRate")}
          // Không có đơn 1–2 sao nào trong tập đã lọc thì tỷ lệ là rỗng, không phải 0%
          // — cùng quy ước với on_time_rate ở trên.
          value={
            kpis.late_related_low_review_rate === null
              ? "—"
              : format.number(kpis.late_related_low_review_rate, "percent")
          }
          hint={t("lowReviewHint")}
        />
      </section>
    </>
  );
}

function StageTile({
  testId,
  label,
  stage,
}: {
  testId: string;
  label: string;
  stage: StageDuration;
}) {
  const t = useTranslations("dashboard");
  const format = useFormatter();
  return (
    <KpiTile
      testId={testId}
      label={label}
      // Chặng có thể toàn NULL (mọi đơn thiếu mốc trung gian trong tập đã lọc); "—"
      // tránh in ra "null ngày" một cách vô nghĩa.
      value={
        stage.median_days === null
          ? "—"
          : t("medianDays", { value: format.number(stage.median_days, "days") })
      }
      hint={
        stage.p90_days === null
          ? undefined
          : t("p90Hint", { value: format.number(stage.p90_days, "days") })
      }
    />
  );
}
