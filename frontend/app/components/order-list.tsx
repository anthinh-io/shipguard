"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useFormatter, useTranslations } from "next-intl";
import { ArrowDown, ArrowUp, ArrowUpDown, Download, Plus, Search } from "lucide-react";

import { apiFetch } from "@/app/lib/api";
import {
  BRL,
  OUTCOME_CLASS,
  RISK_LEVEL_CLASS,
  utcDay,
  type DeliveryOutcome,
  type RiskLevel,
} from "@/app/lib/order-format";
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

const EXPORT_FILENAME = "orders.csv";

// Ô tìm đổi URL và gọi máy chủ, nên phải chờ người dùng ngừng gõ một nhịp.
const SEARCH_DEBOUNCE_MS = 250;

// Mã đơn là chuỗi băm 32 ký tự; 8 ký tự đầu đủ để phân biệt bằng mắt trên một trang.
const SHORT_ID_LENGTH = 8;

type OrderListItem = {
  order_id: string;
  order_status: string;
  delivery_outcome: DeliveryOutcome;
  purchased_at: string;
  estimated_delivery_date: string;
  delivered_at: string | null;
  customer_state: string;
  order_value: number | null;
  risk_level: RiskLevel;
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

function toFailure(error: unknown): Failure {
  return error instanceof OrdersError
    ? error.failure
    : { kind: "network", detail: error instanceof Error ? error.message : String(error) };
}

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

function orderPath(orderId: string): string {
  return `${ORDERS_PATH}/${encodeURIComponent(orderId)}`;
}

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
        setState({ kind: "error", failure: toFailure(error) });
      });
  }, [url]);

  const [exporting, setExporting] = useState(false);
  const [exportFailure, setExportFailure] = useState<Failure | null>(null);

  // Tải qua apiFetch rồi lưu blob chứ không dùng <a href> trỏ thẳng backend: thẻ <a> không
  // mang được header Authorization, nên sẽ nhận 401. Bỏ page vì file gồm mọi trang.
  async function handleExport() {
    setExporting(true);
    setExportFailure(null);
    try {
      if (!BACKEND_URL) {
        throw new OrdersError({ kind: "missing_backend_url" });
      }
      const exportQuery = toOrderListQuery({ ...params, page: 1 });
      const response = await apiFetch(
        `${BACKEND_URL}/orders/export${exportQuery ? `?${exportQuery}` : ""}`,
        { cache: "no-store" },
      );
      if (!response.ok) {
        throw new OrdersError({ kind: "http_status", status: response.status });
      }
      const href = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = href;
      link.download = EXPORT_FILENAME;
      document.body.append(link);
      link.click();
      link.remove();
      // Thu hồi ngay sau click có thể cắt ngang lượt tải; đợi một nhịp cho trình duyệt nhận.
      setTimeout(() => URL.revokeObjectURL(href), 0);
    } catch (error) {
      setExportFailure(toFailure(error));
    } finally {
      setExporting(false);
    }
  }

  function failureDetail(failure: Failure): string {
    return failure.kind === "missing_backend_url"
      ? t("errorDetail.missingBackendUrl")
      : failure.kind === "http_status"
        ? t("errorDetail.httpStatus", { status: failure.status })
        : failure.detail;
  }

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
    content = (
      <p data-testid="orders-error" className="text-red-700 dark:text-red-400">
        {t("error", { detail: failureDetail(state.failure) })}
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
              <TableHead>{t("columns.riskLevel")}</TableHead>
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
              // Bấm vào đâu trên dòng cũng mở đơn; mã đơn là một liên kết thật để còn
              // dùng bàn phím, mở tab mới hay chép đường dẫn. push chứ không replace: Back
              // phải về đúng danh sách này, vốn đã nằm nguyên trên URL.
              <TableRow
                key={item.order_id}
                data-testid="order-row"
                className="cursor-pointer"
                onClick={() => router.push(orderPath(item.order_id))}
              >
                <TableCell>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Link
                        href={orderPath(item.order_id)}
                        data-testid="order-id"
                        className="font-mono hover:underline"
                        onClick={(event) => event.stopPropagation()}
                      >
                        {item.order_id.slice(0, SHORT_ID_LENGTH)}
                      </Link>
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
                  <Badge
                    data-testid="order-risk-level"
                    variant="outline"
                    className={RISK_LEVEL_CLASS[item.risk_level]}
                  >
                    {t(`riskLevel.${item.risk_level}`)}
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
      <div className="flex flex-wrap items-center gap-2">
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
        <Button
          data-testid="orders-export"
          variant="outline"
          size="sm"
          disabled={exporting}
          onClick={handleExport}
        >
          <Download aria-hidden />
          {exporting ? t("exporting") : t("export")}
        </Button>
        <Button data-testid="orders-new" size="sm" onClick={() => router.push("/orders/new")}>
          <Plus aria-hidden />
          {t("new")}
        </Button>
      </div>
      {exportFailure ? (
        <p
          data-testid="orders-export-error"
          className="mt-2 text-sm text-red-700 dark:text-red-400"
        >
          {t("exportError", { detail: failureDetail(exportFailure) })}
        </p>
      ) : null}
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
