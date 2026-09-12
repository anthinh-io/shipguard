"use client";

import { useState } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { CalendarIcon } from "lucide-react";
import type { DateRange } from "react-day-picker";

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

export type Filters = {
  range: { from: string; to: string } | null;
  customerState: string | null;
};

// null ở mỗi trường nghĩa là không gắn tham số đó vào chuỗi truy vấn, chứ không phải
// "gắn giá trị mặc định" — xem dashboard.tsx.
export const EMPTY_FILTERS: Filters = { range: null, customerState: null };

// shadcn Select không chấp nhận value="" cho một item, nên cần một giá trị đặc biệt
// riêng cho lựa chọn "tất cả các bang".
const ALL_STATES = "__all__";

export function FilterBar({
  filters,
  customerStates,
  onChange,
}: {
  filters: Filters;
  customerStates: string[];
  onChange: (filters: Filters) => void;
}) {
  const t = useTranslations("dashboard");
  const format = useFormatter();
  const [open, setOpen] = useState(false);
  // Trạng thái tạm trong lúc người dùng đang chọn khoảng (mới chọn một đầu, chưa chọn
  // đầu kia) — chỉ commit vào filters, và do đó gọi lại máy chủ, khi cả hai đầu đã
  // chọn xong. Khởi tạo từ filters.range để mở lại popover vẫn thấy khoảng đang áp.
  const [pendingRange, setPendingRange] = useState<DateRange | undefined>(
    filters.range
      ? { from: fromISODate(filters.range.from), to: fromISODate(filters.range.to) }
      : undefined,
  );

  const dateRangeLabel = filters.range
    ? `${format.dateTime(fromISODate(filters.range.from), "fullDate")} – ${format.dateTime(
        fromISODate(filters.range.to),
        "fullDate",
      )}`
    : t("filters.pickDateRange");

  function handleRangeSelect(range: DateRange | undefined) {
    setPendingRange(range);
    if (!range?.from || !range?.to) {
      return;
    }
    // Kỳ tối thiểu là 2 ngày: chọn đúng một ngày thì tự nới thành 2, vì một biểu đồ xu
    // hướng của đúng một ngày không nói lên điều gì (xem #9).
    const to =
      range.to.getTime() === range.from.getTime()
        ? new Date(range.from.getTime() + 24 * 60 * 60 * 1000)
        : range.to;
    onChange({
      ...filters,
      range: { from: toISODate(range.from), to: toISODate(to) },
    });
    setOpen(false);
  }

  function handleStateChange(value: string) {
    onChange({ ...filters, customerState: value === ALL_STATES ? null : value });
  }

  function handleClearAll() {
    setPendingRange(undefined);
    onChange(EMPTY_FILTERS);
  }

  return (
    <div data-testid="filter-bar" className="mt-4 flex flex-wrap items-center gap-3">
      <Popover open={open} onOpenChange={setOpen}>
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
          {customerStates.map((state) => (
            <SelectItem key={state} value={state}>
              {state}
            </SelectItem>
          ))}
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
