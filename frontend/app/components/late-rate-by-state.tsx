"use client";

import { useFormatter, useTranslations } from "next-intl";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "./ui/chart";

type StateLateRate = {
  customer_state: string;
  delivered_orders: number;
  late_orders: number;
  late_rate: number;
};

// Một chuỗi số liệu duy nhất nên không cần chú giải màu — tiêu đề đã gọi tên nó.
// --chart-2 chứ không phải --chart-1: bộ token neutral của dự án đặt --chart-1 gần
// trắng, vô hình trên nền sáng.
const chartConfig = {
  late_rate: { color: "var(--chart-2)" },
} satisfies ChartConfig;

export function LateRateByStateChart({
  byState,
}: {
  byState: StateLateRate[];
}) {
  const t = useTranslations("dashboard");
  const format = useFormatter();

  return (
    <Card data-testid="late-rate-by-state">
      <CardHeader>
        <CardTitle>{t("byStateTitle")}</CardTitle>
      </CardHeader>
      <CardContent>
        {/* Biểu đồ cột xếp hạng, không dùng bản đồ: câu hỏi người dùng đang hỏi là "xử
            lý vùng nào trước", và danh sách xếp hạng trả lời trực tiếp hơn một bản đồ
            tô màu. byState đã được backend xếp giảm dần theo late_rate; layout dọc để
            27 bang đọc được thành một danh sách từ trên xuống, chiều cao cố định thay
            cho aspect-video mặc định vì danh sách này cao hơn rộng. */}
        <ChartContainer config={chartConfig} className="aspect-auto h-[560px] w-full">
          <BarChart data={byState} layout="vertical" margin={{ left: 8, right: 16 }}>
            <CartesianGrid horizontal={false} />
            <XAxis
              type="number"
              tickFormatter={(value: number) => format.number(value, "percentAxis")}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              type="category"
              dataKey="customer_state"
              tickLine={false}
              axisLine={false}
              width={40}
              interval={0}
            />
            <ChartTooltip
              content={
                <ChartTooltipContent
                  formatter={(value) => [
                    format.number(value as number, "percent"),
                    t("lateRate"),
                  ]}
                />
              }
            />
            <Bar dataKey="late_rate" fill="var(--color-late_rate)" radius={4} />
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
