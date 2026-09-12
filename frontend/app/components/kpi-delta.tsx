"use client";

import { useFormatter, useTranslations } from "next-intl";
import { ArrowDownIcon, ArrowUpIcon } from "lucide-react";

// Ba loại đơn vị, không gộp được vào một: tỷ lệ chênh nhau theo ĐIỂM phần trăm, số đơn
// chênh nhau theo đơn, ba chặng chênh nhau theo ngày.
export type DeltaUnit = "percentagePoints" | "count" | "days";

type UnitSpec = {
  // Tên format khai trong i18n/request.ts.
  numberFormat: string;
  // Số chữ số thập phân của chính format đó, phải giữ song song với nó. Cần ở đây để
  // xét chiều trên đúng con số người đọc nhìn thấy, chứ không phải trên phần lẻ đã bị
  // giấu đi khi hiển thị.
  precision: number;
  // Tỷ lệ về đây là số thực 0–1; nhân 100 để ra điểm phần trăm.
  scale: number;
  // Khoá i18n bọc quanh con số để gọi tên đơn vị; số đếm không cần đơn vị nào.
  labelKey: string | null;
};

// Một bảng thay cho bốn nhánh rẽ trên cùng một kiểu.
const UNITS: Record<DeltaUnit, UnitSpec> = {
  percentagePoints: {
    numberFormat: "signedPercentagePoints",
    precision: 2,
    scale: 100,
    labelKey: "deltaPercentagePoints",
  },
  count: {
    numberFormat: "signedCount",
    precision: 0,
    scale: 1,
    labelKey: null,
  },
  days: {
    numberFormat: "signedDays",
    precision: 2,
    scale: 1,
    labelKey: "deltaDays",
  },
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

  const spec = UNITS[unit];
  const delta = (value - comparisonValue) * spec.scale;
  // Xét chiều trên con số ĐÃ làm tròn tới đúng độ chính xác được hiển thị: một chênh
  // lệch nhỏ hơn chữ số cuối cùng không được hiện ra thành "+0,00" kèm mũi tên đi lên.
  const rounded = Number(delta.toFixed(spec.precision));
  const rendered = format.number(rounded, spec.numberFormat);
  const label = spec.labelKey ? t(spec.labelKey, { value: rendered }) : rendered;

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
