"use client";

import { useTranslations } from "next-intl";

import {
  EMPTY_FILTERS,
  type ComparisonMode,
  type DashboardFilters,
} from "@/app/lib/dashboard-filters";
import { CustomerStateSelect } from "./customer-state-select";
import { DateRangePicker } from "./date-range-picker";
import { SellerCombobox } from "./seller-combobox";
import { Button } from "./ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";

// Dùng "__none__" chứ không phải "none": shadcn Select không chấp nhận value="" cho một
// item, và đây thuần tuý là giá trị của một mục trong ô chọn, không bao giờ đi lên máy
// chủ (null nghĩa là bỏ hẳn tham số). Trùng tên với literal "none" của backend chỉ gây
// hiểu nhầm rằng hai thứ phải khớp nhau.
const NO_COMPARISON = "__none__";

export function FilterBar({
  filters,
  customerStates,
  onChange,
}: {
  filters: DashboardFilters;
  customerStates: string[];
  onChange: (filters: DashboardFilters) => void;
}) {
  const t = useTranslations("dashboard");

  return (
    <div data-testid="filter-bar" className="mt-4 flex flex-wrap items-center gap-3">
      <DateRangePicker
        range={filters.range}
        onChange={(range) => onChange({ ...filters, range })}
        label={t("filters.dateRange")}
        placeholder={t("filters.pickDateRange")}
        testId="filter-date-range"
        // Kỳ tối thiểu 2 ngày (xem #9): một biểu đồ xu hướng của đúng một ngày không nói
        // lên điều gì.
        min={2}
      />

      <CustomerStateSelect
        value={filters.customerState}
        states={customerStates}
        onChange={(customerState) => onChange({ ...filters, customerState })}
      />

      <SellerCombobox
        sellerId={filters.sellerId}
        onChange={(sellerId) => onChange({ ...filters, sellerId })}
      />

      <Select
        value={filters.comparison ?? NO_COMPARISON}
        onValueChange={(value) =>
          onChange({
            ...filters,
            comparison:
              value === NO_COMPARISON ? null : (value as ComparisonMode),
          })
        }
      >
        <SelectTrigger
          data-testid="filter-comparison"
          aria-label={t("filters.comparison")}
          className="w-[200px]"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={NO_COMPARISON}>
            {t("filters.comparisonNone")}
          </SelectItem>
          <SelectItem value="previous">
            {t("filters.comparisonPrevious")}
          </SelectItem>
          <SelectItem value="year_over_year">
            {t("filters.comparisonYearOverYear")}
          </SelectItem>
        </SelectContent>
      </Select>

      <Button
        variant="ghost"
        size="sm"
        data-testid="filter-clear-all"
        onClick={() => onChange(EMPTY_FILTERS)}
      >
        {t("filters.clearAll")}
      </Button>
    </div>
  );
}
