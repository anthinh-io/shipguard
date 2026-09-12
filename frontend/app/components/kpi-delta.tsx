"use client";

import { useFormatter, useTranslations } from "next-intl";
import { ArrowDownIcon, ArrowUpIcon } from "lucide-react";

// Ba loại đơn vị, không gộp được vào một: tỷ lệ chênh nhau theo ĐIỂM phần trăm, số đơn
// chênh nhau theo đơn, ba chặng chênh nhau theo ngày.
export type DeltaUnit = "percentagePoints" | "count" | "days";

const NUMBER_FORMAT: Record<DeltaUnit, string> = {
  percentagePoints: "signedPercentagePoints",
  count: "signedCount",
  days: "signedDays",
};

// Số chữ số thập phân của từng định dạng trên, giữ song song với i18n/request.ts. Cần
// nó để xét chiều trên đúng con số người đọc nhìn thấy.
const PRECISION: Record<DeltaUnit, number> = {
  percentagePoints: 2,
  count: 0,
  days: 2,
};

export function KpiDelta({
  value,
  comparisonValue,
  unit,
  higherIsBetter,
}: {
  value: number | null;
  comparisonValue: number | null | undefined;
  unit: DeltaUnit;
  // Chiều tốt/xấu khác nhau theo từng chỉ số: đúng hạn tăng là tốt, đơn trễ và ba chặng
  // thời gian tăng là xấu. Không có tham số này thì mũi tên lên trên ô "Đơn giao trễ"
  // sẽ được tô xanh, tức là nói ngược.
  higherIsBetter: boolean;
}) {
  const t = useTranslations("dashboard");
  const format = useFormatter();

  // Thiếu một trong hai vế thì không có mức chênh nào để hiện — không so sánh, hoặc kỳ
  // đối chiếu không có đơn nào. Trả về rỗng chứ không phải "0", vì "không biết" và
  // "không đổi" là hai điều khác nhau.
  if (value === null || comparisonValue === null || comparisonValue === undefined) {
    return null;
  }

  // Tỷ lệ về đây là số thực 0–1; nhân 100 để ra điểm phần trăm.
  const scale = unit === "percentagePoints" ? 100 : 1;
  const delta = (value - comparisonValue) * scale;
  // Xét chiều trên con số ĐÃ làm tròn tới đúng độ chính xác được hiển thị: một chênh
  // lệch nhỏ hơn chữ số cuối cùng không được hiện ra thành "+0,00" kèm mũi tên đi lên.
  const rounded = Number(delta.toFixed(PRECISION[unit]));
  const rendered = format.number(rounded, NUMBER_FORMAT[unit]);
  const label =
    unit === "percentagePoints"
      ? t("deltaPercentagePoints", { value: rendered })
      : unit === "days"
        ? t("deltaDays", { value: rendered })
        : rendered;

  if (rounded === 0) {
    return (
      <p data-testid="kpi-delta" data-direction="flat" className="mt-2 text-sm text-muted-foreground">
        {t("deltaFlat")}
      </p>
    );
  }

  const up = rounded > 0;
  const good = up === higherIsBetter;
  const Arrow = up ? ArrowUpIcon : ArrowDownIcon;

  return (
    <p
      data-testid="kpi-delta"
      data-direction={up ? "up" : "down"}
      className={`mt-2 flex items-center gap-1 text-sm font-medium ${
        good
          ? "text-emerald-700 dark:text-emerald-400"
          : "text-red-700 dark:text-red-400"
      }`}
    >
      {/* Dấu đã nằm trong phần chữ, nên mũi tên chỉ là trang trí. */}
      <Arrow className="size-4" aria-hidden />
      {label}
    </p>
  );
}
