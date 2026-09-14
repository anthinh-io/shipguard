"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useFormatter, useTranslations } from "next-intl";
import { ArrowDown, ArrowUp, ArrowUpDown, Search } from "lucide-react";

import { apiFetch } from "@/app/lib/api";
import {
  hasActiveFilters,
  toOrderListQuery,
  type OrderListParams,
  type OrderSort,
} from "@/app/lib/order-list-params";
import { OrderFilterBar } from "./order-filter-bar";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { InputGroup, InputGroupAddon, InputGroupInput } from "./ui/input-group";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";

// Phải đọc nguyên dạng tĩnh như thế này thì Next mới thay được giá trị lúc build.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

const ORDERS_PATH = "/orders";

// Ô tìm đổi URL và gọi máy chủ, nên phải chờ người dùng ngừng gõ một nhịp.
const SEARCH_DEBOUNCE_MS = 250;

// Mã đơn là chuỗi băm 32 ký tự; 8 ký tự đầu đủ để phân biệt bằng mắt trên một trang.
const SHORT_ID_LENGTH = 8;

// Ngoại lệ có chủ ý với quy tắc "đừng dựng Intl tại chỗ" của README: Order Value là tiền
// Brazil và luôn hiện theo kiểu Brazil "R$ 13.664,08", ở cả hai ngôn ngữ giao diện. Bộ
// định dạng này cố ý không đổi theo nút chuyển ngữ, nên đóng cứng ở phạm vi module là
// đúng — useFormatter luôn dùng ngôn ngữ giao diện và không cho đổi riêng từng lần gọi.
const BRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

type DeliveryOutcome = "on_time" | "late" | "no_outcome";

type OrderListItem = {
  order_id: string;
  order_status: string;
  delivery_outcome: DeliveryOutcome;
  purchased_at: string;
  estimated_delivery_date: string;
  delivered_at: string | null;
  customer_state: string;
  order_value: number | null;
};

type OrderListData = {
  items: OrderListItem[];
  total: number;
  page: number;
  page_size: number;
};

type Failure =
  | { kind: "missing_backend_url" }
  | { kind: "http_status"; status: number }
  // Lỗi mạng do trình duyệt sinh ra, luôn tiếng Anh và không dịch được; giữ nguyên văn.
  | { kind: "network"; detail: string };

class OrdersError extends Error {
  constructor(readonly failure: Failure) {
    super(failure.kind);
  }
}

type State =
  | { kind: "loading" }
  | { kind: "error"; failure: Failure }
  | { kind: "loaded"; data: OrderListData };

async function fetchOrders(url: string): Promise<OrderListData> {
  if (!BACKEND_URL) {
    throw new OrdersError({ kind: "missing_backend_url" });
  }
  const response = await apiFetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new OrdersError({ kind: "http_status", status: response.status });
  }
  return (await response.json()) as OrderListData;
}

// Backend trả dấu thời gian không kèm múi giờ ("2018-10-17T02:30:18"). new Date() đọc
// chuỗi đó theo giờ máy, rồi fullDate hiện theo UTC — máy ở phía đông UTC lùi mất một
// ngày. Cắt lấy phần ngày thì new Date() đọc thành nửa đêm UTC, khớp quy ước ADR-0005.
function utcDay(value: string): Date {
  return new Date(value.slice(0, 10));
}

const OUTCOME_CLASS: Record<DeliveryOutcome, string> = {
  on_time:
    "border-emerald-600/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  late: "border-red-600/30 bg-red-500/10 text-red-700 dark:text-red-400",
  no_outcome: "text-muted-foreground",
};

export function OrderList({ params }: { params: OrderListParams }) {
  const t = useTranslations("orders");
  const format = useFormatter();
  const router = useRouter();
  const [state, setState] = useState<State>({ kind: "loading" });

  const query = toOrderListQuery(params);
  const url = `${BACKEND_URL}/orders${query ? `?${query}` : ""}`;

  const navigate = useCallback(
    (next: OrderListParams, mode: "push" | "replace") => {
      const nextQuery = toOrderListQuery(next);
      router[mode](nextQuery ? `${ORDERS_PATH}?${nextQuery}` : ORDERS_PATH);
    },
    [router],
  );

  // Cùng chốt với dashboard.tsx: nhớ địa chỉ đã gọi để Strict Mode không gọi hai lần và
  // phản hồi của một lần lật trang cũ không đè lên trang mới.
  const requested = useRef<string | null>(null);

  useEffect(() => {
    if (requested.current === url) {
      return;
    }
    requested.current = url;

    fetchOrders(url)
      .then((data) => {
        if (requested.current === url) {
          setState({ kind: "loaded", data });
        }
      })
      .catch((error: unknown) => {
        if (requested.current !== url) {
          return;
        }
        setState({
          kind: "error",
          failure:
            error instanceof OrdersError
              ? error.failure
              : {
                  kind: "network",
                  detail: error instanceof Error ? error.message : String(error),
                },
        });
      });
  }, [url]);

  // Ô tìm giữ chữ đang gõ riêng, vì URL chỉ đổi sau nhịp chờ. Khi URL đổi từ ngoài — nút
  // Back, bấm lại mục sidebar — thì kéo ô tìm theo. Điều chỉnh ngay lúc render chứ không
  // trong effect: react-hooks/set-state-in-effect là lỗi trong cấu hình eslint này.
  const [search, setSearch] = useState(params.orderId);
  const [syncedOrderId, setSyncedOrderId] = useState(params.orderId);
  if (params.orderId !== syncedOrderId) {
    setSyncedOrderId(params.orderId);
    if (search.trim() !== params.orderId) {
      setSearch(params.orderId);
    }
  }

  useEffect(() => {
    const trimmed = search.trim();
    if (trimmed === params.orderId) {
      return;
    }
    // replace chứ không push: mỗi nhịp gõ không đáng một bước trong lịch sử trình duyệt.
    // Tìm mới thì về trang 1 — trang 7 của một tập đơn khác không có nghĩa gì.
    const timer = setTimeout(
      () => navigate({ ...params, orderId: trimmed, page: 1 }, "replace"),
      SEARCH_DEBOUNCE_MS,
    );
    return () => clearTimeout(timer);
  }, [search, params, navigate]);

  function handleSort(column: OrderSort) {
    // Cột mới bắt đầu giảm dần: người dùng bấm cột ngày hay giá trị thường muốn thấy mới
    // nhất hoặc lớn nhất trước. Đổi thứ tự thì về trang 1, cùng lý do với ô tìm.
    const direction =
      params.sort === column && params.direction === "desc" ? "asc" : "desc";
    navigate({ ...params, sort: column, direction, page: 1 }, "push");
  }

  let content: ReactNode;
  if (state.kind === "loading") {
    content = (
      <p data-testid="orders-loading" className="opacity-70">
        {t("loading")}
      </p>
    );
  } else if (state.kind === "error") {
    const { failure } = state;
    const detail =
      failure.kind === "missing_backend_url"
        ? t("errorDetail.missingBackendUrl")
        : failure.kind === "http_status"
          ? t("errorDetail.httpStatus", { status: failure.status })
          : failure.detail;
    content = (
      <p data-testid="orders-error" className="text-red-700 dark:text-red-400">
        {t("error", { detail })}
      </p>
    );
  } else if (state.data.total === 0) {
    // Có bộ lọc nào đang bật thì không nói "không có mã bắt đầu bằng…": mã có thể có thật,
    // chỉ là không thỏa bộ lọc.
    content = (
      <p data-testid="orders-no-match" className="text-muted-foreground">
        {hasActiveFilters(params.filters) || !params.orderId
          ? t("noMatchFilters")
          : t("noMatch", { orderId: params.orderId })}
      </p>
    );
  } else {
    const { items, total, page_size } = state.data;
    const pageCount = Math.ceil(total / page_size);

    content = (
      <>
        <p data-testid="orders-total" className="text-sm text-muted-foreground">
          {t("total", { count: total })}
        </p>
        <Table data-testid="orders-table" className="mt-2">
          <TableHeader>
            <TableRow>
              <TableHead>{t("columns.orderId")}</TableHead>
              <TableHead>{t("columns.status")}</TableHead>
              <TableHead>{t("columns.outcome")}</TableHead>
              <SortableHead column="purchased_at" params={params} onSort={handleSort}>
                {t("columns.purchasedAt")}
              </SortableHead>
              <SortableHead
                column="estimated_delivery_date"
                params={params}
                onSort={handleSort}
              >
                {t("columns.estimatedDeliveryDate")}
              </SortableHead>
              <SortableHead column="delivered_at" params={params} onSort={handleSort}>
                {t("columns.deliveredAt")}
              </SortableHead>
              <TableHead>{t("columns.customerState")}</TableHead>
              <SortableHead
                column="order_value"
                params={params}
                onSort={handleSort}
                className="text-right"
              >
                {t("columns.orderValue")}
              </SortableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.order_id} data-testid="order-row">
                <TableCell>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span data-testid="order-id" tabIndex={0} className="font-mono">
                        {item.order_id.slice(0, SHORT_ID_LENGTH)}
                      </span>
                    </TooltipTrigger>
                    <TooltipContent className="font-mono">{item.order_id}</TooltipContent>
                  </Tooltip>
                </TableCell>
                <TableCell>{t(`status.${item.order_status}`)}</TableCell>
                <TableCell>
                  <Badge
                    data-testid="delivery-outcome"
                    variant="outline"
                    className={OUTCOME_CLASS[item.delivery_outcome]}
                  >
                    {t(`outcome.${item.delivery_outcome}`)}
                  </Badge>
                </TableCell>
                <TableCell>
                  {format.dateTime(utcDay(item.purchased_at), "fullDate")}
                </TableCell>
                <TableCell>
                  {format.dateTime(utcDay(item.estimated_delivery_date), "fullDate")}
                </TableCell>
                <TableCell>
                  {item.delivered_at
                    ? format.dateTime(utcDay(item.delivered_at), "fullDate")
                    : "—"}
                </TableCell>
                <TableCell>{item.customer_state}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {item.order_value === null ? "—" : BRL.format(item.order_value)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {items.length === 0 ? (
          // Chỉ tới được đây bằng một đường liên kết sửa tay có trang vượt quá.
          <div className="mt-4 flex items-center gap-3">
            <p data-testid="orders-page-empty" className="text-muted-foreground">
              {t("pageEmpty")}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate({ ...params, page: 1 }, "push")}
            >
              {t("backToFirst")}
            </Button>
          </div>
        ) : null}
        {/* key theo trang: lật trang xong thì ô nhập dựng lại với số trang mới. */}
        <Pagination
          key={params.page}
          page={params.page}
          pageCount={pageCount}
          onPage={(page) => navigate({ ...params, page }, "push")}
        />
      </>
    );
  }

  return (
    <div data-testid="orders">
      <InputGroup className="max-w-sm">
        <InputGroupAddon>
          <Search aria-hidden />
        </InputGroupAddon>
        <InputGroupInput
          data-testid="orders-search"
          aria-label={t("searchLabel")}
          placeholder={t("searchPlaceholder")}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          spellCheck={false}
          autoComplete="off"
        />
      </InputGroup>
      {/* push chứ không replace: mỗi lần đổi bộ lọc là một bước Back được. Đổi bộ lọc thì
          về trang 1, cùng lý do với ô tìm. */}
      <OrderFilterBar
        filters={params.filters}
        onChange={(filters) => navigate({ ...params, filters, page: 1 }, "push")}
      />
      <div className="mt-4">{content}</div>
    </div>
  );
}

function SortableHead({
  column,
  params,
  onSort,
  className,
  children,
}: {
  column: OrderSort;
  params: OrderListParams;
  onSort: (column: OrderSort) => void;
  className?: string;
  children: ReactNode;
}) {
  const active = params.sort === column;
  const Icon = !active ? ArrowUpDown : params.direction === "asc" ? ArrowUp : ArrowDown;

  return (
    <TableHead
      data-testid={`header-${column}`}
      aria-sort={active ? (params.direction === "asc" ? "ascending" : "descending") : "none"}
      className={className}
    >
      <Button
        data-testid={`sort-${column}`}
        variant="ghost"
        size="sm"
        className="-mx-2.5"
        onClick={() => onSort(column)}
      >
        {children}
        <Icon aria-hidden className={active ? undefined : "opacity-40"} />
      </Button>
    </TableHead>
  );
}

function Pagination({
  page,
  pageCount,
  onPage,
}: {
  page: number;
  pageCount: number;
  onPage: (page: number) => void;
}) {
  const t = useTranslations("orders");
  const [draft, setDraft] = useState(String(page));

  function jump() {
    const requestedPage = Number.parseInt(draft, 10);
    if (Number.isNaN(requestedPage)) {
      setDraft(String(page));
      return;
    }
    // Kẹp vào dải hợp lệ thay vì báo lỗi: gõ 99999 là muốn tới trang cuối.
    const target = Math.min(Math.max(requestedPage, 1), pageCount);
    if (target === page) {
      setDraft(String(page));
      return;
    }
    onPage(target);
  }

  return (
    <nav
      data-testid="orders-pagination"
      aria-label={t("pagination")}
      className="mt-4 flex flex-wrap items-center justify-end gap-2 text-sm"
    >
      <Button
        variant="outline"
        size="sm"
        disabled={page <= 1}
        onClick={() => onPage(Math.min(page - 1, pageCount))}
      >
        {t("previous")}
      </Button>
      <form
        className="flex items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          jump();
        }}
      >
        <label htmlFor="orders-page-input">{t("page")}</label>
        <Input
          id="orders-page-input"
          data-testid="orders-page-input"
          inputMode="numeric"
          className="h-7 w-20 text-center"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        <span data-testid="orders-page-count">
          {t("pageCount", { count: pageCount })}
        </span>
      </form>
      <Button
        variant="outline"
        size="sm"
        disabled={page >= pageCount}
        onClick={() => onPage(page + 1)}
      >
        {t("next")}
      </Button>
    </nav>
  );
}
