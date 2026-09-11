"use client";

import { useEffect, useRef, useState } from "react";

// Phải đọc nguyên dạng tĩnh như thế này thì Next mới thay được giá trị lúc build.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

type ReportingPeriod = {
  start_date: string;
  end_date: string;
};

type Kpis = {
  delivered_orders: number;
  late_orders: number;
  on_time_rate: number | null;
};

type DashboardData = {
  reporting_period: ReportingPeriod | null;
  kpis: Kpis;
};

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "loaded"; data: DashboardData };

const percent = new Intl.NumberFormat("vi-VN", {
  style: "percent",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const integer = new Intl.NumberFormat("vi-VN");
// dateStyle "short" cho năm hai chữ số ("1/9/17"), mơ hồ với một kỳ báo cáo trải nhiều
// năm; nêu rõ từng thành phần để ra 01/09/2017.
//
// timeZone UTC là bắt buộc, không phải tuỳ chọn: new Date("2017-09-01") đọc chuỗi chỉ
// có ngày thành nửa đêm UTC, nên máy đặt ở múi giờ phía tây UTC sẽ hiện 31/08/2017 —
// lệch đúng một ngày ở chính cái ranh giới mà cả tính năng này xoay quanh.
const fullDate = new Intl.DateTimeFormat("vi-VN", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  timeZone: "UTC",
});

async function fetchDashboard(url: string): Promise<DashboardData> {
  // Ném thay vì dựng trạng thái lỗi thẳng trong effect: cả hai hiện ra cùng một chỗ,
  // nhưng ném thì đi qua nhánh catch chung và không gọi setState đồng bộ trong effect.
  if (!BACKEND_URL) {
    throw new Error("thiếu biến môi trường NEXT_PUBLIC_BACKEND_URL");
  }
  const response = await fetch(url, { cache: "no-store" });
  // Phản hồi lỗi của FastAPI vẫn là JSON hợp lệ — 422 khi ngày sai định dạng chẳng
  // hạn — nên phải chặn theo mã trạng thái, không thể chỉ dựa vào json() ném hay không.
  if (!response.ok) {
    throw new Error(`Máy chủ trả về mã ${response.status}`);
  }
  return (await response.json()) as DashboardData;
}

function formatPeriod(period: ReportingPeriod | null): string {
  if (!period) {
    return "chưa có đơn nào đã giao";
  }
  return `${fullDate.format(new Date(period.start_date))} – ${fullDate.format(
    new Date(period.end_date),
  )}`;
}

function KpiTile({
  testId,
  label,
  value,
  hint,
}: {
  testId: string;
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <article
      data-testid={testId}
      className="rounded-lg border border-black/10 p-5 dark:border-white/15"
    >
      <h2 className="text-sm font-medium opacity-70">{label}</h2>
      <p className="mt-2 text-4xl font-semibold tabular-nums">{value}</p>
      {hint ? <p className="mt-2 text-sm opacity-60">{hint}</p> : null}
    </article>
  );
}

export default function Dashboard() {
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
          message: error instanceof Error ? error.message : String(error),
        }),
      );
  }, [url]);

  if (state.kind === "loading") {
    return (
      <p data-testid="dashboard-loading" className="opacity-70">
        Đang tải số liệu…
      </p>
    );
  }

  if (state.kind === "error") {
    return (
      <p data-testid="dashboard-error" className="text-red-700 dark:text-red-400">
        Không lấy được số liệu từ máy chủ ({state.message}). Vui lòng thử lại.
      </p>
    );
  }

  const { reporting_period, kpis } = state.data;

  return (
    <>
      <p data-testid="reporting-period" className="mt-1 opacity-70">
        Kỳ báo cáo: {formatPeriod(reporting_period)}
      </p>
      <section
        data-testid="kpi-grid"
        className="mt-6 grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-4"
      >
        <KpiTile
          testId="kpi-on-time-rate"
          label="Tỷ lệ giao đúng hạn"
          // Kỳ lọc có thể không ra đơn nào; lúc đó tỷ lệ là rỗng chứ không phải 0%.
          value={kpis.on_time_rate === null ? "—" : percent.format(kpis.on_time_rate)}
          hint={`${integer.format(kpis.delivered_orders)} đơn đã giao`}
        />
        <KpiTile
          testId="kpi-late-orders"
          label="Đơn giao trễ"
          value={integer.format(kpis.late_orders)}
        />
      </section>
    </>
  );
}
