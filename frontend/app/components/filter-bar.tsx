"use client";

import { useState } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { CalendarIcon } from "lucide-react";
import type { DateRange } from "react-day-picker";

import { SellerCombobox, type SellerOption } from "./seller-combobox";
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

export type ComparisonMode = "previous" | "year_over_year";

export type Filters = {
  range: { from: string; to: string } | null;
  customerState: string | null;
  // Giữ cả đối tượng chứ không chỉ mã: nhãn trên nút cần bang của người bán, mà không
  // có nơi nào khác để tra lại nó. Chỉ seller_id đi vào chuỗi truy vấn.
  seller: SellerOption | null;
  comparison: ComparisonMode | null;
};

// null ở mỗi trường nghĩa là không gắn tham số đó vào chuỗi truy vấn, chứ không phải
// "gắn giá trị mặc định" — xem dashboard.tsx.
export const EMPTY_FILTERS: Filters = {
  range: null,
  customerState: null,
  seller: null,
  comparison: null,
};

// shadcn Select không chấp nhận value="" cho một item, nên cần một giá trị đặc biệt
// riêng cho lựa chọn "tất cả các bang".
const ALL_STATES = "__all__";
// Cùng lý do, cho chế độ "không so sánh".
const NO_COMPARISON = "none";

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
          {customerStates.map((state) => (
            <SelectItem key={state} value={state}>
              {state}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <SellerCombobox
        seller={filters.seller}
        onChange={(seller) => onChange({ ...filters, seller })}
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
