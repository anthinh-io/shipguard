"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { apiFetch } from "@/app/lib/api";
import {
  DELIVERY_OUTCOMES,
  EMPTY_ORDER_FILTERS,
  ORDER_STATUSES,
  type DeliveryOutcome,
  type OrderFilters,
  type OrderStatus,
} from "@/app/lib/order-list-params";
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

// Phải đọc nguyên dạng tĩnh như thế này thì Next mới thay được giá trị lúc build.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

// shadcn Select không chấp nhận value="" cho một item.
const ALL = "__all__";

export function OrderFilterBar({
  filters,
  onChange,
}: {
  filters: OrderFilters;
  onChange: (filters: OrderFilters) => void;
}) {
  const t = useTranslations("orders");
  const [customerStates, setCustomerStates] = useState<string[]>([]);

  // Danh sách bang không đổi theo trang hay bộ lọc, nên chỉ tải một lần. Hỏng thì ô bang
  // chỉ còn "tất cả các bang" — lỗi của danh sách đơn đã có chỗ hiển thị của nó rồi.
  useEffect(() => {
    if (!BACKEND_URL) {
      return;
    }
    let cancelled = false;
    apiFetch(`${BACKEND_URL}/customer-states`, { cache: "no-store" })
      .then((response) => (response.ok ? (response.json() as Promise<string[]>) : []))
      .then((states) => {
        if (!cancelled) {
          setCustomerStates(states);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div data-testid="order-filter-bar" className="mt-3 flex flex-wrap items-center gap-3">
      <Select
        value={filters.orderStatus ?? ALL}
        onValueChange={(value) =>
          onChange({ ...filters, orderStatus: value === ALL ? null : (value as OrderStatus) })
        }
      >
        <SelectTrigger
          data-testid="filter-order-status"
          aria-label={t("filters.orderStatus")}
          className="w-[180px]"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>{t("filters.allStatuses")}</SelectItem>
          {ORDER_STATUSES.map((status) => (
            <SelectItem key={status} value={status}>
              {t(`status.${status}`)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={filters.deliveryOutcome ?? ALL}
        onValueChange={(value) =>
          onChange({
            ...filters,
            deliveryOutcome: value === ALL ? null : (value as DeliveryOutcome),
          })
        }
      >
        <SelectTrigger
          data-testid="filter-delivery-outcome"
          aria-label={t("filters.deliveryOutcome")}
          className="w-[180px]"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>{t("filters.allOutcomes")}</SelectItem>
          {DELIVERY_OUTCOMES.map((outcome) => (
            <SelectItem key={outcome} value={outcome}>
              {t(`outcome.${outcome}`)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Hai cặp ngày độc lập: Purchase Date là mốc mặc định khi tra đơn vì mọi đơn đều
          có; ngày giao chỉ đơn đã giao mới có. Chọn tháng/năm bằng ô thả xuống vì dữ
          liệu nằm ở 2016–2018, cách hôm nay nhiều năm. */}
      <DateRangePicker
        range={filters.purchased}
        onChange={(purchased) => onChange({ ...filters, purchased })}
        label={t("filters.purchasedRange")}
        placeholder={t("filters.purchasedPlaceholder")}
        testId="filter-purchased-range"
        captionLayout="dropdown"
      />
      <DateRangePicker
        range={filters.delivered}
        onChange={(delivered) => onChange({ ...filters, delivered })}
        label={t("filters.deliveredRange")}
        placeholder={t("filters.deliveredPlaceholder")}
        testId="filter-delivered-range"
        captionLayout="dropdown"
      />

      <CustomerStateSelect
        value={filters.customerState}
        states={customerStates}
        onChange={(customerState) => onChange({ ...filters, customerState })}
      />

      <SellerCombobox
        sellerId={filters.sellerId}
        onChange={(sellerId) => onChange({ ...filters, sellerId })}
        deliveredOnly={false}
      />

      <Button
        variant="ghost"
        size="sm"
        data-testid="filter-clear-all"
        onClick={() => onChange(EMPTY_ORDER_FILTERS)}
      >
        {t("filters.clearAll")}
      </Button>
    </div>
  );
}
