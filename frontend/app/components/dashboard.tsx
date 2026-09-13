"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useFormatter, useTranslations } from "next-intl";

import { apiFetch } from "@/app/lib/api";
import { EMPTY_FILTERS, FilterBar, type Filters } from "./filter-bar";
import { KpiDelta } from "./kpi-delta";
import { KpiTile } from "./kpi-tile";
import { LateRateByStateChart } from "./late-rate-by-state";
import { LateRateTrendChart } from "./late-rate-trend";

// Phải đọc nguyên dạng tĩnh như thế này thì Next mới thay được giá trị lúc build.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

function buildDashboardUrl(filters: Filters): string {
  const params = new URLSearchParams();
  // null nghĩa là không gắn tham số đó — backend tự giải kỳ mặc định hoặc không lọc
  // bang, đúng hành vi "chưa chọn gì" chứ không phải một nhánh riêng.
  if (filters.range) {
    params.set("start_date", filters.range.from);
    params.set("end_date", filters.range.to);
  }
  if (filters.customerState) {
    params.set("customer_state", filters.customerState);
  }
  if (filters.seller) {
    params.set("seller_id", filters.seller.seller_id);
  }
  if (filters.comparison) {
    params.set("comparison", filters.comparison);
  }
  const query = params.toString();
  return `${BACKEND_URL}/dashboard${query ? `?${query}` : ""}`;
}

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

type Granularity = "day" | "week" | "month";

type TrendPoint = {
  bucket_start: string;
  delivered_orders: number;
  late_orders: number;
  late_rate: number | null;
};

type LateRateTrend = {
  granularity: Granularity;
  points: TrendPoint[];
};

type StateLateRate = {
  customer_state: string;
  delivered_orders: number;
  late_orders: number;
  late_rate: number;
};

type FilterOptions = {
  customer_states: string[];
};

type DashboardData = {
  reporting_period: ReportingPeriod | null;
  filter_options: FilterOptions;
  kpis: Kpis;
  late_rate_trend: LateRateTrend;
  late_rate_by_state: StateLateRate[];
  small_sample: boolean;
  // null nghĩa là không so sánh. "Có so sánh nhưng kỳ đối chiếu rỗng" là chuyện khác:
  // lúc đó khối vẫn về đầy đủ với delivered_orders bằng 0 và các tỷ lệ là null.
  comparison_period: ReportingPeriod | null;
  comparison_kpis: Kpis | null;
  comparison_late_rate_trend: LateRateTrend | null;
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
  const response = await apiFetch(url, { cache: "no-store" });
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
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const url = buildDashboardUrl(filters);
  // Strict Mode gọi effect mount hai lần ở chế độ phát triển và không có lớp nào gộp
  // fetch trần, nên không chặn thì mỗi lần mở trang sinh hai lần gọi máy chủ.
  // AbortController không thay thế được chốt này: request đã huỷ vẫn là một request.
  //
  // Chốt nhớ *địa chỉ đã gọi* chứ không phải "đã gọi lần nào chưa". Bộ lọc gắn vào
  // chuỗi truy vấn nên đổi bộ lọc vẫn gọi lại được, còn một cờ boolean sẽ chặn vĩnh
  // viễn sau lần gọi đầu tiên.
  const requested = useRef<string | null>(null);

  useEffect(() => {
    if (requested.current === url) {
      return;
    }
    requested.current = url;

    fetchDashboard(url)
      .then((data) => {
        // Chốt chống phản hồi cũ: nếu người dùng đổi bộ lọc nhanh trước khi lần gọi
        // trước kịp về, requested.current đã trỏ sang địa chỉ mới nhất — chỉ nhận
        // phản hồi khớp đúng địa chỉ mà closure này đã gọi.
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
            error instanceof DashboardError
              ? error.failure
              : {
                  kind: "network",
                  detail: error instanceof Error ? error.message : String(error),
                },
        });
      });
  }, [url]);

  let content: ReactNode;
  if (state.kind === "loading") {
    content = (
      <p data-testid="dashboard-loading" className="opacity-70">
        {t("loading")}
      </p>
    );
  } else if (state.kind === "error") {
    const { failure } = state;
    const detail =
      failure.kind === "missing_backend_url"
        ? t("errorDetail.missingBackendUrl")
        : failure.kind === "http_status"
          ? t("errorDetail.httpStatus", { status: failure.status })
          : failure.detail;

    content = (
      <p data-testid="dashboard-error" className="text-red-700 dark:text-red-400">
        {t("error", { detail })}
      </p>
    );
  } else if (state.data.kpis.delivered_orders === 0) {
    // Bộ lọc không ra đơn nào — một kết quả rỗng hợp lệ, không phải lỗi hệ thống.
    // data-testid riêng để phân biệt rõ với dashboard-error, đúng tiêu chí của #11.
    content = (
      <p data-testid="dashboard-empty" className="text-muted-foreground">
        {t("empty")}
      </p>
    );
  } else {
    const { reporting_period, kpis } = state.data;
    // Hẹp hơn state.data.comparison_kpis một bậc, nên cố ý mang tên khác: kỳ đối chiếu
    // không có đơn nào thì ở đây là null, còn trong phản hồi thì vẫn là một khối đầy đủ.
    //
    // Không có đơn nào để so thì không hiện mức chênh nào cả — kể cả với số đơn trễ, chỉ
    // số duy nhất mà 0 là một giá trị hợp lệ. "45 đơn so với một kỳ rỗng" đọc ra thành
    // "tăng 45 đơn", trong khi thật ra là không có gì để so. Các tỷ lệ đã tự rỗng theo
    // quy ước của backend; chốt này kéo số đếm về cùng một hành vi.
    const comparisonKpis =
      state.data.comparison_kpis && state.data.comparison_kpis.delivered_orders > 0
        ? state.data.comparison_kpis
        : null;
    const period = reporting_period
      ? `${format.dateTime(new Date(reporting_period.start_date), "fullDate")} – ${format.dateTime(
          new Date(reporting_period.end_date),
          "fullDate",
        )}`
      : t("noDeliveredOrders");

    content = (
      <>
        <p data-testid="reporting-period" className="mt-1 opacity-70">
          {t("reportingPeriod", { period })}
        </p>
        {/* Cảnh báo, không phải che giấu: lưới KPI bên dưới vẫn hiện đủ mọi con số.
            Người dùng có quyền xem, chỉ cần biết là đừng kết luận chắc từ đó. */}
        {state.data.small_sample ? (
          <p
            data-testid="small-sample-warning"
            role="status"
            className="mt-4 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-900 dark:text-amber-200"
          >
            {t("smallSampleWarning", { count: kpis.delivered_orders })}
          </p>
        ) : null}
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
            delta={
              <KpiDelta
                value={kpis.on_time_rate}
                comparisonValue={comparisonKpis?.on_time_rate}
                unit="percentagePoints"
                // Chỉ số duy nhất mà tăng là tốt.
                higherIsBetter
              />
            }
          />
          <KpiTile
            testId="kpi-late-orders"
            label={t("lateOrders")}
            value={format.number(kpis.late_orders)}
            delta={
              <KpiDelta
                value={kpis.late_orders}
                comparisonValue={comparisonKpis?.late_orders}
                unit="count"
                higherIsBetter={false}
              />
            }
          />
          <StageTile
            testId="kpi-payment-approval"
            label={t("paymentApproval")}
            stage={kpis.payment_approval}
            comparisonStage={comparisonKpis?.payment_approval}
          />
          <StageTile
            testId="kpi-seller-handling"
            label={t("sellerHandling")}
            stage={kpis.seller_handling}
            comparisonStage={comparisonKpis?.seller_handling}
          />
          <StageTile
            testId="kpi-carrier-transit"
            label={t("carrierTransit")}
            stage={kpis.carrier_transit}
            comparisonStage={comparisonKpis?.carrier_transit}
          />
          <KpiTile
            testId="kpi-late-related-low-review-rate"
            label={t("lateRelatedLowReviewRate")}
            // Không có đơn 1–2 sao nào trong tập đã lọc thì tỷ lệ là rỗng, không phải
            // 0% — cùng quy ước với on_time_rate ở trên.
            value={
              kpis.late_related_low_review_rate === null
                ? "—"
                : format.number(kpis.late_related_low_review_rate, "percent")
            }
            hint={t("lowReviewHint")}
            delta={
              <KpiDelta
                value={kpis.late_related_low_review_rate}
                comparisonValue={comparisonKpis?.late_related_low_review_rate}
                unit="percentagePoints"
                higherIsBetter={false}
              />
            }
          />
        </section>
        {/* Quy ước "giao đúng ngày cam kết là đúng hạn" được đóng cứng vào cột sinh
            is_late, nhưng người đọc không nhìn thấy lược đồ. Nói thẳng ra ở đây thì
            con số trên lưới KPI mới khớp với cách quản lý vẫn hiểu về lời hứa với
            khách. Dòng chú thích chứ không phải tooltip: mục đích là người đọc biết
            quy ước, mà tooltip thì phải rê chuột mới thấy. */}
        <p
          data-testid="on-time-definition"
          className="mt-3 text-sm text-muted-foreground"
        >
          {t("onTimeDefinition")}
        </p>
        <div className="mt-6">
          <LateRateTrendChart
            trend={state.data.late_rate_trend}
            comparison={state.data.comparison_late_rate_trend}
          />
        </div>
        <div className="mt-6">
          <LateRateByStateChart byState={state.data.late_rate_by_state} />
        </div>
      </>
    );
  }

  return (
    <>
      {/* Luôn vẽ, kể cả khi đang tải hoặc lỗi — bộ lọc là nơi người dùng phải quay
          lại nếu vừa lọc hỏng, nên nó không được biến mất đúng lúc cần nhất. */}
      <FilterBar
        filters={filters}
        customerStates={
          state.kind === "loaded" ? state.data.filter_options.customer_states : []
        }
        onChange={setFilters}
      />
      {content}
    </>
  );
}

function StageTile({
  testId,
  label,
  stage,
  comparisonStage,
}: {
  testId: string;
  label: string;
  stage: StageDuration;
  comparisonStage?: StageDuration;
}) {
  const t = useTranslations("dashboard");
  const format = useFormatter();
  return (
    <KpiTile
      testId={testId}
      label={label}
      // Mức chênh tính trên trung vị, cùng con số đang hiện lớn ở giữa ô. Chặng chậm đi
      // là xấu, nên không có chỉ số nào ở đây tăng mà tốt.
      delta={
        <KpiDelta
          value={stage.median_days}
          comparisonValue={comparisonStage?.median_days}
          unit="days"
          higherIsBetter={false}
        />
      }
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
