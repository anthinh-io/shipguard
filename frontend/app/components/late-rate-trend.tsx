"use client";

import { useFormatter, useTranslations } from "next-intl";
import {
  CartesianGrid,
  Line,
  LineChart,
  XAxis,
  YAxis,
  type MouseHandlerDataParam,
} from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "./ui/chart";

type Granularity = "day" | "week" | "month";

type TrendPoint = {
  bucket_start: string;
  // Khoảng thật của nhóm, backend đã kẹp vào kỳ báo cáo — drill-down chép nguyên.
  bucket_from: string;
  bucket_to: string;
  delivered_orders: number;
  late_orders: number;
  late_rate: number | null;
};

type LateRateTrend = {
  granularity: Granularity;
  points: TrendPoint[];
};

export function LateRateTrendChart({
  trend,
  comparison,
  onPointClick,
}: {
  trend: LateRateTrend;
  comparison?: LateRateTrend | null;
  // Luôn nhận điểm của kỳ đang xem, kể cả khi bấm lên đường kỳ đối chiếu: kỳ so sánh
  // không mang sang danh sách đơn.
  onPointClick?: (point: TrendPoint) => void;
}) {
  const t = useTranslations("dashboard");
  const format = useFormatter();

  // Gắn vào cả biểu đồ chứ không vào từng chấm: vùng click trùng vùng hiện tooltip có
  // gợi ý, nên không có chỗ nào gợi ý hiện ra mà bấm lại không đi đâu. activeIndex của
  // recharts 3 là chuỗi, và rỗng khi bấm ngoài vùng vẽ.
  function handleChartClick({ activeIndex }: MouseHandlerDataParam) {
    const point = activeIndex == null ? undefined : trend.points[Number(activeIndex)];
    if (point && onPointClick) {
      onPointClick(point);
    }
  }

  // Dựng trong component chứ không phải ở tầng module: ChartLegendContent chỉ đọc
  // `label` của chartConfig và không nhận formatter nào, nên nhãn phải được dịch ngay
  // tại đây thì chú giải mới đổi theo ngôn ngữ đang chọn.
  //
  // --chart-2 chứ không phải --chart-1: bộ token neutral của dự án đặt --chart-1 gần
  // trắng, vô hình trên nền sáng. Bộ token này không có màu (chroma 0), nên hai đường
  // chỉ khác nhau về độ sáng — nét đứt và chú giải mới là thứ phân biệt chúng.
  const chartConfig = {
    late_rate: { color: "var(--chart-2)", label: t("trendCurrentSeries") },
    comparison_late_rate: {
      color: "var(--chart-3)",
      label: t("trendComparisonSeries"),
    },
  } satisfies ChartConfig;

  // Độ mịn theo tháng dùng nhãn "thg 1 2018"; ngày và tuần dùng "01/01" — tuần không
  // có format riêng vì mốc của nó vốn đã là một ngày cụ thể (thứ Hai đầu tuần).
  const axisFormat = trend.granularity === "month" ? "axisMonth" : "axisDate";

  const data = trend.points.map((point, index) => {
    // Ghép hai chuỗi theo CHỈ SỐ nhóm, không theo ngày: kỳ đối chiếu có bucket_start
    // khác hẳn nên trên một trục ngày nó sẽ rơi ra ngoài vùng vẽ. Trục hoành giữ ngày
    // của kỳ chính, nhóm thứ i của kỳ đối chiếu úp lên nhóm thứ i của kỳ chính.
    //
    // Hai chuỗi lệch số nhóm chỉ xảy ra ở rìa năm nhuận; lúc đó phần dư của kỳ đối
    // chiếu bị bỏ, vì không có vị trí nào trên trục để đặt nó.
    const other = comparison?.points[index];
    return {
      ...point,
      // new Date trên chuỗi chỉ có ngày đọc thành nửa đêm UTC; format bên dưới khai
      // timeZone: "UTC" nên không lệch ngày — cùng cơ chế với reporting-period.
      date: new Date(point.bucket_start),
      comparison_late_rate: other ? other.late_rate : null,
      comparison_bucket_start: other ? other.bucket_start : null,
    };
  });

  return (
    <Card
      data-testid="late-rate-trend"
      data-granularity={trend.granularity}
      data-comparison={comparison ? "on" : "off"}
    >
      <CardHeader>
        <CardTitle>{t("trendTitle")}</CardTitle>
        <CardDescription>{t(`granularity.${trend.granularity}`)}</CardDescription>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig}>
          {/* Con trỏ đặt qua style chứ không qua class trên ChartContainer: recharts
              ghi cứng cursor: default lên .recharts-wrapper bằng style nội tuyến. */}
          <LineChart
            data={data}
            margin={{ left: 4, right: 12 }}
            onClick={onPointClick ? handleChartClick : undefined}
            style={onPointClick ? { cursor: "pointer" } : undefined}
          >
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={(value: Date) => format.dateTime(value, axisFormat)}
              tickLine={false}
              axisLine={false}
              minTickGap={24}
            />
            <YAxis
              tickFormatter={(value: number) => format.number(value, "percentAxis")}
              tickLine={false}
              axisLine={false}
              width={48}
            />
            <ChartTooltip
              content={
                <ChartTooltipContent
                  labelFormatter={(_, payload) => {
                    const row = payload?.[0]?.payload as
                      | { bucket_start: string; comparison_bucket_start: string | null }
                      | undefined;
                    if (!row) {
                      return "";
                    }
                    const current = format.dateTime(
                      new Date(row.bucket_start),
                      "fullDate",
                    );
                    // Hai nhóm úp lên nhau theo chỉ số nhưng là hai ngày khác nhau;
                    // không nói ra thì người đọc tưởng cả hai đường cùng một mốc.
                    const label = row.comparison_bucket_start
                      ? `${current} ↔ ${format.dateTime(
                          new Date(row.comparison_bucket_start),
                          "fullDate",
                        )}`
                      : current;
                    return onPointClick ? (
                      <>
                        {label}
                        <div className="font-normal text-muted-foreground">
                          {t("drillDownHint")}
                        </div>
                      </>
                    ) : (
                      label
                    );
                  }}
                  formatter={(value, name) => [
                    value === null || value === undefined
                      ? "—"
                      : format.number(value as number, "percent"),
                    name === "comparison_late_rate"
                      ? t("trendComparisonSeries")
                      : t("lateRate"),
                  ]}
                />
              }
            />
            {comparison ? <ChartLegend content={<ChartLegendContent />} /> : null}
            {/* connectNulls mặc định là false: nhóm rỗng (late_rate null) để lại một
                khoảng hở trên đường, đúng ý nghĩa "không có đơn nào" thay vì vẽ tiếp
                như thể tỷ lệ bằng 0%. Có chấm ở mỗi điểm thật (dot khác false): một
                điểm có dữ liệu nhưng cả hai lân cận đều rỗng sẽ không có đoạn nào để
                vẽ — thiếu chấm thì điểm đó biến mất hoàn toàn khỏi biểu đồ. */}
            <Line
              dataKey="late_rate"
              stroke="var(--color-late_rate)"
              strokeWidth={2}
              dot={{ r: 3, fill: "var(--color-late_rate)", strokeWidth: 0 }}
            />
            {comparison ? (
              <Line
                dataKey="comparison_late_rate"
                stroke="var(--color-comparison_late_rate)"
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={{
                  r: 3,
                  fill: "var(--color-comparison_late_rate)",
                  strokeWidth: 0,
                }}
              />
            ) : null}
          </LineChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
