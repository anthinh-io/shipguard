"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { ChevronsUpDownIcon } from "lucide-react";

import { apiFetch } from "@/app/lib/api";
import { Button } from "./ui/button";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "./ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";

// Phải đọc nguyên dạng tĩnh như thế này thì Next mới thay được giá trị lúc build.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

type SellerOption = {
  seller_id: string;
  // Seller State theo CONTEXT.md: bang người bán gửi hàng đi, không phải bang khách
  // nhận. Ở đây nó chỉ để nhận diện người bán trong danh sách gợi ý.
  seller_city: string;
  seller_state: string;
  delivered_orders: number;
};

// Ô gọi máy chủ theo từng phím gõ, nên phải chờ người dùng ngừng gõ một nhịp.
const SUGGESTION_DEBOUNCE_MS = 250;

// Mã người bán là chuỗi băm 32 ký tự trông giống hệt nhau; cắt ngắn cho dễ đọc, phần
// phân biệt thật sự nằm ở bang, thành phố và số đơn đi kèm.
const SHORT_ID_LENGTH = 8;

function shortId(sellerId: string): string {
  return sellerId.slice(0, SHORT_ID_LENGTH);
}

export function SellerCombobox({
  sellerId,
  onChange,
}: {
  sellerId: string | null;
  onChange: (sellerId: string | null) => void;
}) {
  const t = useTranslations("dashboard");
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<SellerOption[]>([]);
  // Người bán đã chọn hoặc đã tra ra, theo mã: chọn từ gợi ý thì không tốn thêm lần gọi
  // nào, và bấm Back qua lại giữa vài người bán cũng không tra lại.
  const [known, setKnown] = useState<Record<string, SellerOption>>({});
  const current = sellerId ? known[sellerId] : undefined;

  // URL chỉ mang seller_id, mà nhãn cần bang của người bán. /sellers khớp tiền tố trên
  // mã, và mã đủ 32 ký tự là tiền tố của chính nó; vẫn lọc đúng mã cho chắc, vì cùng
  // chuỗi đó cũng được đem khớp với bang và thành phố.
  useEffect(() => {
    if (!BACKEND_URL || !sellerId || current) {
      return;
    }
    let cancelled = false;
    apiFetch(`${BACKEND_URL}/sellers?q=${encodeURIComponent(sellerId)}`, {
      cache: "no-store",
    })
      .then((response) =>
        response.ok ? (response.json() as Promise<SellerOption[]>) : [],
      )
      .then((data) => {
        const match = data.find((option) => option.seller_id === sellerId);
        if (!cancelled && match) {
          setKnown((previous) => ({ ...previous, [match.seller_id]: match }));
        }
      })
      // Tra không ra thì nút vẫn hiện mã rút gọn — thiếu bang không làm sai nghĩa.
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [sellerId, current]);

  useEffect(() => {
    const trimmed = query.trim();
    let cancelled = false;
    // Mọi setState nằm trong callback của timer, không phải thân effect: quy tắc
    // react-hooks/set-state-in-effect là lỗi trong cấu hình eslint của dự án này.
    const timer = setTimeout(() => {
      if (!BACKEND_URL || !trimmed) {
        if (!cancelled) {
          setOptions([]);
        }
        return;
      }
      apiFetch(`${BACKEND_URL}/sellers?q=${encodeURIComponent(trimmed)}`, {
        cache: "no-store",
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error(String(response.status));
          }
          return response.json() as Promise<SellerOption[]>;
        })
        .then((data) => {
          if (!cancelled) {
            setOptions(data);
          }
        })
        .catch(() => {
          // Gợi ý hỏng thì đơn giản là không có gợi ý. Ô tìm không dựng trạng thái lỗi
          // riêng — lỗi của bảng điều khiển đã có chỗ hiển thị của nó rồi.
          if (!cancelled) {
            setOptions([]);
          }
        });
    }, SUGGESTION_DEBOUNCE_MS);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query]);

  function handleSelect(option: SellerOption | null) {
    if (option) {
      setKnown((previous) => ({ ...previous, [option.seller_id]: option }));
    }
    onChange(option?.seller_id ?? null);
    setOpen(false);
    setQuery("");
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          role="combobox"
          aria-expanded={open}
          data-testid="filter-seller"
          aria-label={t("filters.seller")}
          className="w-[240px] justify-between font-normal"
        >
          <span className="truncate">
            {/* Có sellerId là phải hiện người bán, kể cả khi chưa tra ra bang: nút ghi
                "tất cả người bán" trong khi số liệu đang lọc theo một người là nói sai
                với người đọc. */}
            {sellerId
              ? `${shortId(sellerId)}…${current ? ` · ${current.seller_state}` : ""}`
              : t("filters.allSellers")}
          </span>
          <ChevronsUpDownIcon className="opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[320px] p-0" align="start">
        {/* Việc khớp nằm ở máy chủ — cmdk mặc định tự lọc lại danh sách trả về theo
            chuỗi đang gõ, và lọc hai lần thì gợi ý khớp theo bang hay thành phố sẽ bị
            chính nó loại đi vì mã băm không chứa chuỗi đó. */}
        <Command shouldFilter={false}>
          <CommandInput
            value={query}
            onValueChange={setQuery}
            placeholder={t("filters.sellerPlaceholder")}
            data-testid="filter-seller-input"
          />
          <CommandList>
            <CommandEmpty>{t("filters.sellerNoResults")}</CommandEmpty>
            {sellerId ? (
              <CommandItem
                value="__all__"
                onSelect={() => handleSelect(null)}
                data-testid="seller-option-all"
              >
                {t("filters.allSellers")}
              </CommandItem>
            ) : null}
            {options.map((option) => (
              <CommandItem
                key={option.seller_id}
                value={option.seller_id}
                onSelect={() => handleSelect(option)}
                data-testid="seller-option"
              >
                <span className="flex flex-col gap-0.5">
                  <span className="font-medium tabular-nums">
                    {shortId(option.seller_id)}…
                  </span>
                  {/* Bang và số đơn là hai thứ duy nhất phân biệt được các dòng gợi ý
                      với nhau — xem #12. */}
                  <span className="text-muted-foreground text-xs">
                    {t("filters.sellerHint", {
                      state: option.seller_state,
                      city: option.seller_city,
                      count: option.delivered_orders,
                    })}
                  </span>
                </span>
              </CommandItem>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
