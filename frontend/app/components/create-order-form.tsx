"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { apiFetch } from "@/app/lib/api";
import { toLocalInputValue } from "@/app/lib/order-format";
import { createOrder, mapFieldErrors, type PaymentType } from "@/app/lib/orders-api";
import { OrderStateSelect } from "./order-state-select";
import { SellerCombobox } from "./seller-combobox";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Input } from "./ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

// Phải đọc nguyên dạng tĩnh như thế này thì Next mới thay được giá trị lúc build.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

const PAYMENT_TYPES: PaymentType[] = ["credit_card", "boleto", "voucher", "debit_card"];

type ProductLine = {
  sellerId: string | null;
  category: string;
  weight: string;
  price: string;
  freight: string;
};

type PaymentLine = {
  type: PaymentType;
  amount: string;
  installments: string;
};

type ProductCategoryOption = { name: string; label: string };

function emptyProductLine(): ProductLine {
  return { sellerId: null, category: "", weight: "", price: "", freight: "" };
}

function emptyPaymentLine(): PaymentLine {
  return { type: "credit_card", amount: "", installments: "1" };
}

type FieldErrors = { byPath: Record<string, string>; formLevel: string[] };

export function CreateOrderForm() {
  const t = useTranslations("createOrder");
  const tPayments = useTranslations("orderDetail");
  const router = useRouter();

  // Chốt một lần lúc mount: input datetime có max cố định bằng thời điểm mở trang, không
  // đuổi theo đồng hồ mỗi lần render.
  const [now] = useState(() => new Date());
  const [purchasedAtInput, setPurchasedAtInput] = useState(() => toLocalInputValue(now));
  const [estimatedDeliveryDate, setEstimatedDeliveryDate] = useState(() =>
    toLocalInputValue(now).slice(0, 10),
  );
  const [customerState, setCustomerState] = useState("");
  const [customerCity, setCustomerCity] = useState("");
  const [customerZip, setCustomerZip] = useState("");
  const [items, setItems] = useState<ProductLine[]>([emptyProductLine()]);
  const [payments, setPayments] = useState<PaymentLine[]>([emptyPaymentLine()]);
  const [categories, setCategories] = useState<ProductCategoryOption[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors | null>(null);
  // Hai luật kiểm ở trình duyệt trước submit (purchased_at trong tương lai, ngày cam kết
  // sớm hơn ngày đặt): thông báo đã dịch sẵn, khác fieldErrors — vốn luôn là chuỗi tiếng
  // Anh thô của Pydantic khi thật sự đến từ máy chủ.
  const [clientError, setClientError] = useState<string | null>(null);
  const [submitFailure, setSubmitFailure] = useState<"modelNotReady" | "unreachable" | null>(
    null,
  );

  useEffect(() => {
    if (!BACKEND_URL) {
      return;
    }
    let cancelled = false;
    apiFetch(`${BACKEND_URL}/product-categories`, { cache: "no-store" })
      .then((response) =>
        response.ok ? (response.json() as Promise<ProductCategoryOption[]>) : [],
      )
      .then((data) => {
        if (!cancelled) {
          setCategories(data);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  // Ngày cam kết không được sớm hơn ngày đặt theo lịch UTC (_estimated_delivery_date_not_
  // before_purchase) — cùng phép so với backend, không so theo lịch riêng của trình duyệt.
  const purchasedAtDate = new Date(purchasedAtInput || now.toISOString());
  const purchasedAtUtcDay = purchasedAtDate.toISOString().slice(0, 10);

  function updateItem(index: number, patch: Partial<ProductLine>) {
    setItems((current) =>
      current.map((item, i) => (i === index ? { ...item, ...patch } : item)),
    );
  }

  function updatePayment(index: number, patch: Partial<PaymentLine>) {
    setPayments((current) =>
      current.map((payment, i) => (i === index ? { ...payment, ...patch } : payment)),
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFieldErrors(null);
    setClientError(null);
    setSubmitFailure(null);

    // Chặn hai luật của NewOrder trước khi gửi, để round-trip qua máy chủ hiếm khi cần
    // (_purchased_at_is_a_real_moment, _estimated_delivery_date_not_before_purchase).
    if (purchasedAtDate.getTime() > Date.now()) {
      setClientError(t("errors.purchasedAtFuture"));
      return;
    }
    if (estimatedDeliveryDate < purchasedAtUtcDay) {
      setClientError(t("errors.deliveryBeforePurchase"));
      return;
    }

    // form có noValidate (banner lỗi tự vẽ thay vì tooltip trình duyệt), nên "required"
    // trên các ô số không tự chặn submit — để trống thì Number("") ra 0, một giá trị hợp
    // lệ với backend (Field(ge=0)), nên đơn được tạo với giá/phí/số tiền 0 một cách âm
    // thầm thay vì bị từ chối. Phải tự kiểm rỗng trước khi parse.
    const blankNumberErrors: Record<string, string> = {};
    items.forEach((item, index) => {
      if (item.price.trim() === "") {
        blankNumberErrors[`items.${index}.price`] = t("errors.required");
      }
      if (item.freight.trim() === "") {
        blankNumberErrors[`items.${index}.freight_value`] = t("errors.required");
      }
    });
    payments.forEach((payment, index) => {
      if (payment.amount.trim() === "") {
        blankNumberErrors[`payments.${index}.payment_value`] = t("errors.required");
      }
    });
    if (Object.keys(blankNumberErrors).length > 0) {
      setFieldErrors({ byPath: blankNumberErrors, formLevel: [] });
      return;
    }

    setSubmitting(true);
    const result = await createOrder({
      purchased_at: purchasedAtDate.toISOString(),
      estimated_delivery_date: estimatedDeliveryDate,
      customer_state: customerState,
      customer_city: customerCity,
      customer_zip_code_prefix: customerZip,
      items: items.map((item) => ({
        seller_id: item.sellerId ?? "",
        product_category_name: item.category,
        product_weight_g: item.weight.trim() === "" ? null : Number(item.weight),
        price: Number(item.price),
        freight_value: Number(item.freight),
      })),
      payments: payments.map((payment) => ({
        payment_type: payment.type,
        payment_installments: Number(payment.installments),
        payment_value: Number(payment.amount),
      })),
    });
    setSubmitting(false);

    if (result.kind === "ok") {
      router.push(`/orders/${result.orderId}`);
      return;
    }
    if (result.kind === "invalid") {
      setFieldErrors(mapFieldErrors(result.errors));
      return;
    }
    setSubmitFailure(result.kind);
  }

  const formLevelMessage =
    clientError ??
    (fieldErrors && fieldErrors.formLevel.length > 0
      ? t("errors.formLevel", { detail: fieldErrors.formLevel.join("; ") })
      : null) ??
    (submitFailure ? t(`errors.${submitFailure}`) : null);

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6" noValidate>
      <Card>
        <CardHeader>
          <CardTitle>{t("title")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-1.5">
              <span>{t("purchasedAt")}</span>
              <Input
                data-testid="create-order-purchased-at"
                type="datetime-local"
                value={purchasedAtInput}
                max={toLocalInputValue(now)}
                onChange={(event) => setPurchasedAtInput(event.target.value)}
                required
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span>{t("committedDeliveryDate")}</span>
              <Input
                data-testid="create-order-delivery-date"
                type="date"
                value={estimatedDeliveryDate}
                min={purchasedAtUtcDay}
                onChange={(event) => setEstimatedDeliveryDate(event.target.value)}
                required
              />
            </label>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <label className="flex flex-col gap-1.5">
              <span>{t("address.state")}</span>
              <OrderStateSelect value={customerState} onChange={setCustomerState} />
              {fieldErrors?.byPath["customer_state"] ? (
                <FieldError message={fieldErrors.byPath["customer_state"]} />
              ) : null}
            </label>
            <label className="flex flex-col gap-1.5">
              <span>{t("address.city")}</span>
              <Input
                data-testid="create-order-city"
                value={customerCity}
                onChange={(event) => setCustomerCity(event.target.value)}
                required
              />
              {fieldErrors?.byPath["customer_city"] ? (
                <FieldError message={fieldErrors.byPath["customer_city"]} />
              ) : null}
            </label>
            <label className="flex flex-col gap-1.5">
              <span>{t("address.zip")}</span>
              <Input
                data-testid="create-order-zip"
                value={customerZip}
                onChange={(event) => setCustomerZip(event.target.value)}
                required
              />
              {fieldErrors?.byPath["customer_zip_code_prefix"] ? (
                <FieldError message={fieldErrors.byPath["customer_zip_code_prefix"]} />
              ) : null}
            </label>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("products.title")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {items.map((item, index) => (
            <div
              key={index}
              data-testid="create-order-item"
              className="flex flex-col gap-3 rounded-md border p-3"
            >
              {fieldErrors?.byPath[`items.${index}`] ? (
                <FieldError message={fieldErrors.byPath[`items.${index}`]} />
              ) : null}
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="flex flex-col gap-1.5">
                  <span>{t("products.seller")}</span>
                  <SellerCombobox
                    sellerId={item.sellerId}
                    onChange={(sellerId) => updateItem(index, { sellerId })}
                    deliveredOnly={false}
                  />
                  {fieldErrors?.byPath[`items.${index}.seller_id`] ? (
                    <FieldError message={fieldErrors.byPath[`items.${index}.seller_id`]} />
                  ) : null}
                </label>
                <label className="flex flex-col gap-1.5">
                  <span>{t("products.category")}</span>
                  <Select
                    value={item.category}
                    onValueChange={(value) => updateItem(index, { category: value })}
                  >
                    <SelectTrigger data-testid="create-order-category" className="w-full">
                      <SelectValue placeholder={t("products.category")} />
                    </SelectTrigger>
                    <SelectContent>
                      {categories.map((category) => (
                        <SelectItem key={category.name} value={category.name}>
                          {category.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {fieldErrors?.byPath[`items.${index}.product_category_name`] ? (
                    <FieldError
                      message={fieldErrors.byPath[`items.${index}.product_category_name`]}
                    />
                  ) : null}
                </label>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <label className="flex flex-col gap-1.5">
                  <span>{t("products.weight")}</span>
                  <Input
                    data-testid="create-order-weight"
                    type="number"
                    min="0"
                    step="1"
                    value={item.weight}
                    onChange={(event) => updateItem(index, { weight: event.target.value })}
                  />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span>{t("products.price")}</span>
                  <Input
                    data-testid="create-order-price"
                    type="number"
                    min="0"
                    step="0.01"
                    value={item.price}
                    onChange={(event) => updateItem(index, { price: event.target.value })}
                    required
                  />
                  {fieldErrors?.byPath[`items.${index}.price`] ? (
                    <FieldError message={fieldErrors.byPath[`items.${index}.price`]} />
                  ) : null}
                </label>
                <label className="flex flex-col gap-1.5">
                  <span>{t("products.freight")}</span>
                  <Input
                    data-testid="create-order-freight"
                    type="number"
                    min="0"
                    step="0.01"
                    value={item.freight}
                    onChange={(event) => updateItem(index, { freight: event.target.value })}
                    required
                  />
                  {fieldErrors?.byPath[`items.${index}.freight_value`] ? (
                    <FieldError message={fieldErrors.byPath[`items.${index}.freight_value`]} />
                  ) : null}
                </label>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="self-end"
                data-testid="create-order-remove-item"
                disabled={items.length === 1}
                onClick={() => setItems((current) => current.filter((_, i) => i !== index))}
              >
                {t("products.remove")}
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="self-start"
            data-testid="create-order-add-item"
            onClick={() => setItems((current) => [...current, emptyProductLine()])}
          >
            {t("products.add")}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("payments.title")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {payments.map((payment, index) => (
            <div
              key={index}
              data-testid="create-order-payment"
              className="flex flex-col gap-3 rounded-md border p-3"
            >
              {fieldErrors?.byPath[`payments.${index}`] ? (
                <FieldError message={fieldErrors.byPath[`payments.${index}`]} />
              ) : null}
              <div className="grid gap-3 sm:grid-cols-3">
                <label className="flex flex-col gap-1.5">
                  <span>{t("payments.type")}</span>
                  <Select
                    value={payment.type}
                    onValueChange={(value) =>
                      updatePayment(index, {
                        type: value as PaymentType,
                        // Số kỳ trả góp chỉ có nghĩa với thẻ tín dụng; đổi hình thức khác
                        // thì khoá về "1" ngay từ phía trình duyệt (_installments_need_
                        // credit_card không có trường lá cụ thể để trỏ tới).
                        installments: value === "credit_card" ? payment.installments : "1",
                      })
                    }
                  >
                    <SelectTrigger data-testid="create-order-payment-type" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PAYMENT_TYPES.map((type) => (
                        <SelectItem key={type} value={type}>
                          {tPayments(`payments.types.${type}`)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </label>
                <label className="flex flex-col gap-1.5">
                  <span>{t("payments.amount")}</span>
                  <Input
                    data-testid="create-order-payment-amount"
                    type="number"
                    min="0"
                    step="0.01"
                    value={payment.amount}
                    onChange={(event) => updatePayment(index, { amount: event.target.value })}
                    required
                  />
                  {fieldErrors?.byPath[`payments.${index}.payment_value`] ? (
                    <FieldError message={fieldErrors.byPath[`payments.${index}.payment_value`]} />
                  ) : null}
                </label>
                <label className="flex flex-col gap-1.5">
                  <span>{t("payments.installments")}</span>
                  <Input
                    data-testid="create-order-payment-installments"
                    type="number"
                    min="1"
                    step="1"
                    value={payment.installments}
                    disabled={payment.type !== "credit_card"}
                    onChange={(event) =>
                      updatePayment(index, { installments: event.target.value })
                    }
                  />
                </label>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="self-end"
                data-testid="create-order-remove-payment"
                disabled={payments.length === 1}
                onClick={() => setPayments((current) => current.filter((_, i) => i !== index))}
              >
                {t("payments.remove")}
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="self-start"
            data-testid="create-order-add-payment"
            onClick={() => setPayments((current) => [...current, emptyPaymentLine()])}
          >
            {t("payments.add")}
          </Button>
        </CardContent>
      </Card>

      {formLevelMessage ? (
        <p
          data-testid="create-order-error"
          role="alert"
          className="text-sm text-red-700 dark:text-red-400"
        >
          {formLevelMessage}
        </p>
      ) : null}

      <Button
        data-testid="create-order-submit"
        type="submit"
        className="self-end"
        disabled={submitting}
      >
        {submitting ? t("submitting") : t("submit")}
      </Button>
    </form>
  );
}

function FieldError({ message }: { message: string }) {
  return (
    <p role="alert" className="text-sm text-red-700 dark:text-red-400">
      {message}
    </p>
  );
}
