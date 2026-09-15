"use client";

import { useRef } from "react";
import { useFormatter, useTranslations } from "next-intl";
import {
  Bar,
  BarChart,
  CartesianGrid,
  XAxis,
  YAxis,
  type MouseHandlerDataParam,
} from "recharts";

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
  onStateClick,
}: {
  byState: StateLateRate[];
  onStateClick?: (customerState: string) => void;
}) {
  const t = useTranslations("dashboard");
  const format = useFormatter();

  // Gắn vào cả biểu đồ chứ không vào <Bar>: tooltip có gợi ý hiện khi rê lên cả dải
  // ngang của bang, và bang tỷ lệ thấp có cột rất ngắn. Cùng cách với late-rate-trend.tsx.
  //
  // Chạm, hay bấm khi chưa rê, thì chưa có activeIndex: cột ghi lại bang bị nhấn lúc
  // mousedown, và chỉ handler này push — mỗi cú bấm đúng một lần.
  const pressedIndex = useRef<number | null>(null);

  function handleChartClick({ activeIndex }: MouseHandlerDataParam) {
    const index = pressedIndex.current ?? (activeIndex == null ? null : Number(activeIndex));
    pressedIndex.current = null;
    const row = index == null ? undefined : byState[index];
    if (row && onStateClick) {
      onStateClick(row.customer_state);
    }
  }

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
          {/* style chứ không phải class: recharts ghi cứng cursor: default nội tuyến. */}
          <BarChart
            data={byState}
            layout="vertical"
            margin={{ left: 8, right: 16 }}
            onClick={onStateClick ? handleChartClick : undefined}
            // Nhấn xuống cột rồi kéo ra ngoài mới nhả thì không có click nào.
            onMouseLeave={() => {
              pressedIndex.current = null;
            }}
            style={onStateClick ? { cursor: "pointer" } : undefined}
          >
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
                  labelFormatter={(label) =>
                    onStateClick ? (
                      <>
                        {label}
                        <div className="font-normal text-muted-foreground">
                          {t("drillDownHint")}
                        </div>
                      </>
                    ) : (
                      label
                    )
                  }
                  formatter={(value) => [
                    format.number(value as number, "percent"),
                    t("lateRate"),
                  ]}
                />
              }
            />
            <Bar
              dataKey="late_rate"
              fill="var(--color-late_rate)"
              radius={4}
              onMouseDown={(_, index) => {
                pressedIndex.current = index;
              }}
            />
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
