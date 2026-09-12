"use client";

import { useFormatter, useTranslations } from "next-intl";
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "./ui/chart";

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

// Một chuỗi số liệu duy nhất nên không cần chú giải màu — tiêu đề đã gọi tên nó.
// --chart-2 chứ không phải --chart-1: bộ token neutral của dự án đặt --chart-1 gần
// trắng, vô hình trên nền sáng.
const chartConfig = {
  late_rate: { color: "var(--chart-2)" },
} satisfies ChartConfig;

export function LateRateTrendChart({ trend }: { trend: LateRateTrend }) {
  const t = useTranslations("dashboard");
  const format = useFormatter();

  // Độ mịn theo tháng dùng nhãn "thg 1 2018"; ngày và tuần dùng "01/01" — tuần không
  // có format riêng vì mốc của nó vốn đã là một ngày cụ thể (thứ Hai đầu tuần).
  const axisFormat = trend.granularity === "month" ? "axisMonth" : "axisDate";

  const data = trend.points.map((point) => ({
    ...point,
    // new Date trên chuỗi chỉ có ngày đọc thành nửa đêm UTC; format bên dưới khai
    // timeZone: "UTC" nên không lệch ngày — cùng cơ chế với reporting-period.
    date: new Date(point.bucket_start),
  }));

  return (
    <Card data-testid="late-rate-trend" data-granularity={trend.granularity}>
      <CardHeader>
        <CardTitle>{t("trendTitle")}</CardTitle>
        <CardDescription>{t(`granularity.${trend.granularity}`)}</CardDescription>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig}>
          <LineChart data={data} margin={{ left: 4, right: 12 }}>
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
                  labelFormatter={(_, payload) =>
                    payload?.[0]
                      ? format.dateTime(
                          new Date(payload[0].payload.bucket_start as string),
                          "fullDate",
                        )
                      : ""
                  }
                  formatter={(value) => [
                    value === null || value === undefined
                      ? "—"
                      : format.number(value as number, "percent"),
                    t("lateRate"),
                  ]}
                />
              }
            />
            {/* connectNulls mặc định là false: nhóm rỗng (late_rate null) để lại một
                khoảng hở trên đường, đúng ý nghĩa "không có đơn nào" thay vì vẽ tiếp
                như thể tỷ lệ bằng 0%. */}
            <Line
              dataKey="late_rate"
              stroke="var(--color-late_rate)"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
