"use client";

import { useState } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { CalendarIcon } from "lucide-react";
import type { DateRange } from "react-day-picker";

import {
  EMPTY_FILTERS,
  type ComparisonMode,
  type DashboardFilters,
} from "@/app/lib/dashboard-filters";
import { SellerCombobox } from "./seller-combobox";
import { Button } from "./ui/button";
import { Calendar } from "./ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
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
// Cùng lý do, cho chế độ "không so sánh". Dùng "__none__" chứ không phải "none": đây
// thuần tuý là giá trị của một mục trong ô chọn, không bao giờ đi lên máy chủ (null
// nghĩa là bỏ hẳn tham số). Trùng tên với literal "none" của backend chỉ gây hiểu nhầm
// rằng hai thứ phải khớp nhau.
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
  const format = useFormatter();
  const [open, setOpen] = useState(false);
  // Trạng thái tạm trong lúc người dùng đang chọn khoảng (mới chọn một đầu, chưa chọn
  // đầu kia) — chỉ commit vào filters, và do đó gọi lại máy chủ, khi cả hai đầu đã
  // chọn xong.
  const [pendingRange, setPendingRange] = useState<DateRange | undefined>(() =>
    toDateRange(filters.range),
  );

  // Danh sách bang đi kèm phản hồi /dashboard, nên lúc đang tải hay tải hỏng thì nó rỗng.
  // Radix Select chỉ hiện được giá trị có mục tương ứng; thiếu mục thì ô bang để trống
  // trong khi đường liên kết đang lọc theo bang đó.
  const stateOptions =
    filters.customerState && !customerStates.includes(filters.customerState)
      ? [filters.customerState, ...customerStates]
      : customerStates;

  const dateRangeLabel = filters.range
    ? `${format.dateTime(fromISODate(filters.range.from), "fullDate")} – ${format.dateTime(
        fromISODate(filters.range.to),
        "fullDate",
      )}`
    : t("filters.pickDateRange");

  // Nạp lại mỗi lần mở chứ không chỉ lúc khởi tạo: bấm Back đổi filters.range mà không
  // dựng lại thanh bộ lọc, và popover phải thấy khoảng đang áp chứ không phải khoảng của
  // lần chọn trước.
  function handleOpenChange(next: boolean) {
    if (next) {
      setPendingRange(toDateRange(filters.range));
    }
    setOpen(next);
  }

  function handleRangeSelect(range: DateRange | undefined) {
    setPendingRange(range);
    // `min={2}` trên Calendar bên dưới đã bắt react-day-picker giữ range ở trạng thái
    // dở dang (to: undefined) cho tới khi đủ hai ngày cách nhau ít nhất một ngày, nên
    // tới đây range.from && range.to là đã đủ điều kiện — không cần tự nới thêm.
    // Không tự làm việc đó ở đây: một lần chọn xong tự nới thì cú nhấp đầu tiên sẽ
    // luôn commit và đóng popover ngay, không còn cách nào chọn một khoảng rộng hơn.
    if (!range?.from || !range?.to) {
      return;
    }
    onChange({
      ...filters,
      range: { from: toISODate(range.from), to: toISODate(range.to) },
    });
    setOpen(false);
  }

  function handleStateChange(value: string) {
    onChange({ ...filters, customerState: value === ALL_STATES ? null : value });
  }

  function handleClearAll() {
    onChange(EMPTY_FILTERS);
  }

  return (
    <div data-testid="filter-bar" className="mt-4 flex flex-wrap items-center gap-3">
      <Popover open={open} onOpenChange={handleOpenChange}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            data-testid="filter-date-range"
            aria-label={t("filters.dateRange")}
          >
            <CalendarIcon />
            {dateRangeLabel}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <Calendar
            mode="range"
            selected={pendingRange}
            onSelect={handleRangeSelect}
            numberOfMonths={2}
            // Kỳ tối thiểu 2 ngày (xem #9): một biểu đồ xu hướng của đúng một ngày
            // không nói lên điều gì. react-day-picker tự giữ range ở trạng thái dở
            // dang cho tới khi đủ điều kiện này, nên cú nhấp đầu tiên không tự đóng
            // popover và người dùng vẫn chọn được một khoảng rộng bất kỳ.
            min={2}
          />
        </PopoverContent>
      </Popover>

      <Select
        value={filters.customerState ?? ALL_STATES}
        onValueChange={handleStateChange}
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
          {stateOptions.map((state) => (
            <SelectItem key={state} value={state}>
              {state}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

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
        onClick={handleClearAll}
      >
        {t("filters.clearAll")}
      </Button>
    </div>
  );
}

// new Date("2018-01-01") đọc chuỗi chỉ có ngày thành nửa đêm UTC — nhất quán với cách
// dashboard.tsx đọc reporting_period, nên hiển thị không lệch ngày dù format khai UTC.
function fromISODate(value: string): Date {
  return new Date(value);
}

function toDateRange(range: DashboardFilters["range"]): DateRange | undefined {
  return range ? { from: fromISODate(range.from), to: fromISODate(range.to) } : undefined;
}

// Ngược lại: Date người dùng chọn trên lịch là giờ địa phương lúc nửa đêm.
// toISOString() quy về UTC nên sẽ lùi một ngày ở múi giờ phía đông UTC; lấy từng
// trường theo giờ địa phương rồi ghép tay để tránh lệch ngày đúng ở ranh giới mà cả
// tính năng này xoay quanh.
function toISODate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
