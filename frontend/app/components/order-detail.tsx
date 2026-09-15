"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useFormatter, useTranslations } from "next-intl";

import { apiFetch } from "@/app/lib/api";
import {
  BRL,
  OUTCOME_CLASS,
  utcDay,
  utcTimestamp,
  type DeliveryOutcome,
} from "@/app/lib/order-format";
import { OrderNotes } from "./order-notes";
import { Badge } from "./ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

// Phải đọc nguyên dạng tĩnh như thế này thì Next mới thay được giá trị lúc build.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

type OrderDetailData = {
  order_id: string;
  order_status: string;
  delivery_outcome: DeliveryOutcome;
  order_value: number | null;
  timeline: {
    purchased_at: string;
    payment_approved_at: string | null;
    handed_to_carrier_at: string | null;
    delivered_at: string | null;
    estimated_delivery_date: string;
    payment_approval_days: number | null;
    seller_handling_days: number | null;
    carrier_transit_days: number | null;
  };
  address: {
    customer_city: string | null;
    customer_state: string;
    customer_zip_code_prefix: string | null;
  };
  items: {
    order_item_id: number;
    product_id: string;
    category: string | null;
    price: number;
    freight_value: number;
    seller_id: string;
  }[];
  sellers: { seller_id: string; seller_city: string; seller_state: string }[];
  payments: {
    payment_sequential: number;
    payment_type: string;
    payment_installments: number;
    payment_value: number;
  }[];
  reviews: {
    review_score: number;
    comment_title: string | null;
    comment_message: string | null;
    created_at: string;
  }[];
};

type Failure =
  | { kind: "missing_backend_url" }
  | { kind: "http_status"; status: number }
  // Lỗi mạng do trình duyệt sinh ra, luôn tiếng Anh và không dịch được; giữ nguyên văn.
  | { kind: "network"; detail: string };

class OrderDetailError extends Error {
  constructor(readonly failure: Failure) {
    super(failure.kind);
  }
}

type State =
  | { kind: "loading" }
  | { kind: "error"; failure: Failure }
  | { kind: "not_found" }
  | { kind: "loaded"; data: OrderDetailData };

// null nghĩa là 404: đường liên kết mang một mã không có thật — một trạng thái của trang,
// không phải lỗi máy chủ.
async function fetchOrder(url: string): Promise<OrderDetailData | null> {
  if (!BACKEND_URL) {
    throw new OrderDetailError({ kind: "missing_backend_url" });
  }
  const response = await apiFetch(url, { cache: "no-store" });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new OrderDetailError({ kind: "http_status", status: response.status });
  }
  return (await response.json()) as OrderDetailData;
}

export function OrderDetail({ orderId }: { orderId: string }) {
  const t = useTranslations("orderDetail");
  const tOrders = useTranslations("orders");
  const [state, setState] = useState<State>({ kind: "loading" });
  const url = `${BACKEND_URL}/orders/${encodeURIComponent(orderId)}`;

  // Cùng chốt với order-list.tsx: Strict Mode không gọi hai lần, và phản hồi của đơn cũ
  // không đè lên đơn mới.
  const requested = useRef<string | null>(null);

  useEffect(() => {
    if (requested.current === url) {
      return;
    }
    requested.current = url;

    fetchOrder(url)
      .then((data) => {
        if (requested.current === url) {
          setState(data ? { kind: "loaded", data } : { kind: "not_found" });
        }
      })
      .catch((error: unknown) => {
        if (requested.current !== url) {
          return;
        }
        setState({
          kind: "error",
          failure:
            error instanceof OrderDetailError
              ? error.failure
              : {
                  kind: "network",
                  detail: error instanceof Error ? error.message : String(error),
                },
        });
      });
  }, [url]);

  if (state.kind === "loading") {
    return (
      <p data-testid="order-detail-loading" className="opacity-70">
        {t("loading")}
      </p>
    );
  }
  if (state.kind === "not_found") {
    return (
      <p data-testid="order-detail-not-found" className="text-muted-foreground break-all">
        {t("notFound", { orderId })}
      </p>
    );
  }
  if (state.kind === "error") {
    const { failure } = state;
    const detail =
      failure.kind === "missing_backend_url"
        ? tOrders("errorDetail.missingBackendUrl")
        : failure.kind === "http_status"
          ? tOrders("errorDetail.httpStatus", { status: failure.status })
          : failure.detail;
    return (
      <p data-testid="order-detail-error" className="text-red-700 dark:text-red-400">
        {t("error", { detail })}
      </p>
    );
  }

  const { data } = state;

  return (
    <div data-testid="order-detail">
      <header className="flex flex-col gap-2">
        <h1 data-testid="order-detail-id" className="font-mono text-lg font-semibold break-all">
          {data.order_id}
        </h1>
        <div className="flex flex-wrap items-center gap-2">
          <Badge data-testid="order-detail-status" variant="secondary">
            {tOrders(`status.${data.order_status}`)}
          </Badge>
          <Badge
            data-testid="order-detail-outcome"
            variant="outline"
            className={OUTCOME_CLASS[data.delivery_outcome]}
          >
            {tOrders(`outcome.${data.delivery_outcome}`)}
          </Badge>
          <span data-testid="order-detail-value" className="text-sm text-muted-foreground">
            {t("orderValue")}:{" "}
            {data.order_value === null ? t("notAvailable") : BRL.format(data.order_value)}
          </span>
        </div>
      </header>

      {/* Ba cột ở màn rộng: nội dung chiếm hai, cột thứ ba là ghi chú nội bộ, dính khi
          cuộn. Màn hẹp thì một cột, và vì ghi chú đứng sau nội dung trong DOM nên nằm cuối
          trang. */}
      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="flex min-w-0 flex-col gap-6 lg:col-span-2">
          <Timeline data={data} />
          <Items data={data} />
          <Sellers data={data} />
          <Address data={data} />
          <Payments data={data} />
          <Reviews data={data} />
        </div>
        {/* Giới hạn cao bằng màn hình trừ top-4 hai đầu và cuộn riêng: không thì ghi chú
            dài hơn một màn hình chỉ đọc được khi cuộn tới cuối trang. */}
        <aside
          data-testid="order-notes-column"
          className="min-w-0 lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:self-start lg:overflow-y-auto"
        >
          <OrderNotes orderId={data.order_id} />
        </aside>
      </div>
    </div>
  );
}

function Section({
  title,
  testId,
  children,
}: {
  title: string;
  testId: string;
  children: ReactNode;
}) {
  return (
    <Card data-testid={testId}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

// Nhãn và giá trị xếp dọc ở màn hẹp, hai cột ở màn rộng hơn — không bao giờ cuộn ngang.
function Field({
  label,
  testId,
  children,
}: {
  label: string;
  testId?: string;
  children: ReactNode;
}) {
  return (
    <div className="grid gap-0.5 sm:grid-cols-[12rem_1fr] sm:gap-4">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd data-testid={testId} className="min-w-0 break-words">
        {children}
      </dd>
    </div>
  );
}

function Timeline({ data }: { data: OrderDetailData }) {
  const t = useTranslations("orderDetail");
  const format = useFormatter();
  const { timeline } = data;

  const moment = (value: string | null) =>
    value === null ? t("notAvailable") : format.dateTime(utcTimestamp(value), "fullDateTime");
  const days = (value: number | null) =>
    value === null
      ? t("notAvailable")
      : t("stages.days", { value: format.number(value, "days") });

  return (
    <Section title={t("timeline.title")} testId="order-timeline">
      <dl className="flex flex-col gap-2">
        <Field label={t("timeline.purchasedAt")} testId="timeline-purchased-at">
          {moment(timeline.purchased_at)}
        </Field>
        <Field label={t("timeline.paymentApprovedAt")} testId="timeline-payment-approved-at">
          {moment(timeline.payment_approved_at)}
        </Field>
        <Field label={t("timeline.handedToCarrierAt")} testId="timeline-handed-to-carrier-at">
          {moment(timeline.handed_to_carrier_at)}
        </Field>
        <Field label={t("timeline.deliveredAt")} testId="timeline-delivered-at">
          {moment(timeline.delivered_at)}
        </Field>
        {/* Đặt ngay dưới ngày giao để so bằng mắt. Ngày cam kết là một ngày, không có giờ. */}
        <Field
          label={t("timeline.estimatedDeliveryDate")}
          testId="timeline-estimated-delivery-date"
        >
          {format.dateTime(utcDay(timeline.estimated_delivery_date), "fullDate")}
        </Field>
      </dl>
      <h3 className="mt-4 mb-2 text-sm font-medium">{t("stages.title")}</h3>
      <dl className="flex flex-col gap-2">
        <Field label={t("stages.paymentApproval")} testId="stage-payment-approval">
          {days(timeline.payment_approval_days)}
        </Field>
        <Field label={t("stages.sellerHandling")} testId="stage-seller-handling">
          {days(timeline.seller_handling_days)}
        </Field>
        <Field label={t("stages.carrierTransit")} testId="stage-carrier-transit">
          {days(timeline.carrier_transit_days)}
        </Field>
      </dl>
    </Section>
  );
}

function Items({ data }: { data: OrderDetailData }) {
  const t = useTranslations("orderDetail");

  return (
    <Section title={t("items.title")} testId="order-items">
      {data.items.length === 0 ? (
        <p data-testid="order-items-empty" className="text-muted-foreground">
          {t("items.empty")}
        </p>
      ) : (
        <ul className="flex flex-col divide-y">
          {data.items.map((item) => (
            <li key={item.order_item_id} data-testid="order-item" className="py-3 first:pt-0 last:pb-0">
              <dl className="flex flex-col gap-1">
                <Field label={t("items.category")}>
                  {item.category ?? t("notAvailable")}
                </Field>
                <Field label={t("items.price")}>{BRL.format(item.price)}</Field>
                <Field label={t("items.freight")}>{BRL.format(item.freight_value)}</Field>
                <Field label={t("items.seller")}>
                  <span className="font-mono break-all">{item.seller_id}</span>
                </Field>
              </dl>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

function Sellers({ data }: { data: OrderDetailData }) {
  const t = useTranslations("orderDetail");

  return (
    <Section title={t("sellers.title")} testId="order-sellers">
      {data.sellers.length === 0 ? (
        <p className="text-muted-foreground">{t("sellers.empty")}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {data.sellers.map((seller) => (
            <li key={seller.seller_id} data-testid="order-seller" className="min-w-0">
              <span className="font-mono break-all">{seller.seller_id}</span>
              <span className="text-muted-foreground">
                {" "}
                · {seller.seller_city} · {seller.seller_state}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

function Address({ data }: { data: OrderDetailData }) {
  const t = useTranslations("orderDetail");
  const { address } = data;

  return (
    <Section title={t("address.title")} testId="order-address">
      <dl className="flex flex-col gap-2">
        <Field label={t("address.city")}>{address.customer_city ?? t("notAvailable")}</Field>
        <Field label={t("address.state")}>{address.customer_state}</Field>
        <Field label={t("address.zip")}>
          {address.customer_zip_code_prefix ?? t("notAvailable")}
        </Field>
      </dl>
    </Section>
  );
}

function Payments({ data }: { data: OrderDetailData }) {
  const t = useTranslations("orderDetail");

  return (
    <Section title={t("payments.title")} testId="order-payments">
      {data.payments.length === 0 ? (
        <p data-testid="order-payments-empty" className="text-muted-foreground">
          {t("payments.empty")}
        </p>
      ) : (
        <ul className="flex flex-col divide-y">
          {data.payments.map((payment) => (
            <li
              key={payment.payment_sequential}
              data-testid="order-payment"
              className="py-3 first:pt-0 last:pb-0"
            >
              <dl className="flex flex-col gap-1">
                <Field label={t("payments.type")}>
                  {/* Hình thức lạ ngoài năm giá trị của Olist thì hiện nguyên mã. */}
                  {t.has(`payments.types.${payment.payment_type}`)
                    ? t(`payments.types.${payment.payment_type}`)
                    : payment.payment_type}
                </Field>
                <Field label={t("payments.installments")}>{payment.payment_installments}</Field>
                <Field label={t("payments.value")}>{BRL.format(payment.payment_value)}</Field>
              </dl>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

function Reviews({ data }: { data: OrderDetailData }) {
  const t = useTranslations("orderDetail");

  return (
    <Section title={t("reviews.title")} testId="order-reviews">
      {data.reviews.length === 0 ? (
        <p data-testid="order-review-empty" className="text-muted-foreground">
          {t("reviews.empty")}
        </p>
      ) : (
        <ul className="flex flex-col gap-3">
          {/* Không có mã đánh giá nào đi kèm, và hai đánh giá có thể trùng ngày tạo. */}
          {data.reviews.map((review, index) => (
            <li key={`${review.created_at}-${index}`} data-testid="order-review" className="min-w-0">
              <p className="font-medium">{t("reviews.score", { score: review.review_score })}</p>
              {review.comment_title ? <p className="font-medium">{review.comment_title}</p> : null}
              <p className="break-words text-muted-foreground">
                {review.comment_message ?? t("reviews.noComment")}
              </p>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}
