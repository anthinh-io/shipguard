"use client";

import { useTranslations } from "next-intl";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";

// shadcn Select không chấp nhận value="" cho một item, nên cần một giá trị đặc biệt
// riêng cho lựa chọn "tất cả các bang".
const ALL_STATES = "__all__";

export function CustomerStateSelect({
  value,
  states,
  onChange,
}: {
  value: string | null;
  states: string[];
  onChange: (state: string | null) => void;
}) {
  const t = useTranslations("dashboard");

  // Danh sách bang tải riêng, nên lúc đang tải hay tải hỏng thì nó rỗng. Radix Select chỉ
  // hiện được giá trị có mục tương ứng; thiếu mục thì ô bang để trống trong khi đường
  // liên kết đang lọc theo bang đó.
  const options = value && !states.includes(value) ? [value, ...states] : states;

  return (
    <Select
      value={value ?? ALL_STATES}
      onValueChange={(next) => onChange(next === ALL_STATES ? null : next)}
    >
      <SelectTrigger
        data-testid="filter-customer-state"
        aria-label={t("filters.customerState")}
        className="w-[180px]"
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL_STATES}>{t("filters.allStates")}</SelectItem>
        {options.map((state) => (
          <SelectItem key={state} value={state}>
            {state}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
