"use client";

import { useState } from "react";
import { useFormatter } from "next-intl";
import { CalendarIcon } from "lucide-react";
import type { DateRange } from "react-day-picker";

import type { DayRange } from "@/app/lib/search-params";
import { Button } from "./ui/button";
import { Calendar } from "./ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";

export function DateRangePicker({
  range,
  onChange,
  label,
  placeholder,
  testId,
  min = 1,
  captionLayout,
}: {
  range: DayRange | null;
  onChange: (range: DayRange) => void;
  label: string;
  placeholder: string;
  testId: string;
  // Số ngày tối thiểu giữa hai đầu, theo nghĩa của react-day-picker. Phải lớn hơn 0: với
  // 0, cú nhấp đầu tiên đã cho ra một khoảng đủ hai đầu và commit ngay.
  min?: number;
  captionLayout?: "label" | "dropdown";
}) {
  const format = useFormatter();
  const [open, setOpen] = useState(false);
  // Trạng thái tạm trong lúc người dùng đang chọn khoảng (mới chọn một đầu, chưa chọn
  // đầu kia) — chỉ commit, và do đó gọi lại máy chủ, khi cả hai đầu đã chọn xong.
  const [pendingRange, setPendingRange] = useState<DateRange | undefined>(() =>
    toDateRange(range),
  );

  const buttonLabel = range
    ? `${format.dateTime(fromISODate(range.from), "fullDate")} – ${format.dateTime(
        fromISODate(range.to),
        "fullDate",
      )}`
    : placeholder;

  // Nạp lại mỗi lần mở chứ không chỉ lúc khởi tạo: bấm Back đổi range mà không dựng lại
  // thanh bộ lọc, và popover phải thấy khoảng đang áp chứ không phải khoảng của lần chọn
  // trước.
  function handleOpenChange(next: boolean) {
    if (next) {
      setPendingRange(toDateRange(range));
    }
    setOpen(next);
  }

  function handleSelect(next: DateRange | undefined) {
    setPendingRange(next);
    // `min` trên Calendar bên dưới đã bắt react-day-picker giữ range ở trạng thái dở dang
    // (to: undefined) cho tới khi đủ điều kiện, nên tới đây next.from && next.to là đã
    // đủ — không cần tự nới thêm. Không tự làm việc đó ở đây: một lần chọn xong tự nới
    // thì cú nhấp đầu tiên sẽ luôn commit và đóng popover ngay, không còn cách nào chọn
    // một khoảng rộng hơn.
    if (!next?.from || !next?.to) {
      return;
    }
    onChange({ from: toISODate(next.from), to: toISODate(next.to) });
    setOpen(false);
  }

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" data-testid={testId} aria-label={label}>
          <CalendarIcon />
          {buttonLabel}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="range"
          selected={pendingRange}
          onSelect={handleSelect}
          numberOfMonths={2}
          min={min}
          captionLayout={captionLayout}
        />
      </PopoverContent>
    </Popover>
  );
}

// new Date("2018-01-01") đọc chuỗi chỉ có ngày thành nửa đêm UTC — nhất quán với format
// fullDate khai UTC, nên nhãn trên nút không lệch ngày.
function fromISODate(value: string): Date {
  return new Date(value);
}

// Lịch làm việc theo giờ địa phương, nên khoảng đưa vào lịch phải là nửa đêm giờ địa
// phương — khác fromISODate, vốn chỉ để hiện nhãn qua format UTC. Dùng nửa đêm UTC ở
// đây thì máy phía tây UTC thấy ngày đầu lùi một ngày, và toISODate ghi lùi luôn khi
// người dùng chọn tiếp.
function toCalendarDate(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function toDateRange(range: DayRange | null): DateRange | undefined {
  return range ? { from: toCalendarDate(range.from), to: toCalendarDate(range.to) } : undefined;
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
