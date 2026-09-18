"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { apiFetch } from "@/app/lib/api";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

// Phải đọc nguyên dạng tĩnh như thế này thì Next mới thay được giá trị lúc build.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

// Không dùng chung CustomerStateSelect (app/components/customer-state-select.tsx): nó
// hardcode sentinel "tất cả các bang" và onChange nhận null cho ngữ nghĩa lọc — biểu mẫu
// tạo đơn luôn cần một bang thật, không có lựa chọn "tất cả".
export function OrderStateSelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (state: string) => void;
}) {
  const t = useTranslations("createOrder");
  const [states, setStates] = useState<string[]>([]);

  useEffect(() => {
    if (!BACKEND_URL) {
      return;
    }
    let cancelled = false;
    apiFetch(`${BACKEND_URL}/customer-states`, { cache: "no-store" })
      .then((response) => (response.ok ? (response.json() as Promise<string[]>) : []))
      .then((data) => {
        if (!cancelled) {
          setStates(data);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger
        data-testid="create-order-state"
        aria-label={t("address.state")}
        className="w-full"
      >
        <SelectValue placeholder={t("address.state")} />
      </SelectTrigger>
      <SelectContent>
        {states.map((state) => (
          <SelectItem key={state} value={state}>
            {state}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
