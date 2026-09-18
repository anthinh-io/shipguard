import { apiFetch } from "./api";

// Phải đọc nguyên dạng tĩnh như thế này thì Next mới thay được giá trị lúc build.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

export type PaymentType = "credit_card" | "boleto" | "voucher" | "debit_card";

export type NewOrderItem = {
  seller_id: string;
  product_category_name: string;
  product_weight_g: number | null;
  price: number;
  freight_value: number;
};

export type NewOrderPayment = {
  payment_type: PaymentType;
  payment_installments: number;
  payment_value: number;
};

export type NewOrder = {
  purchased_at: string;
  estimated_delivery_date: string;
  customer_state: string;
  customer_city: string;
  customer_zip_code_prefix: string;
  items: NewOrderItem[];
  payments: NewOrderPayment[];
};

// Mảng detail 422 của Pydantic; loc có thể mang cả chỉ số phần tử (items.0.seller_id) lẫn
// tên trường thẳng ("body" cho ba model_validator không trỏ được tới trường lá cụ thể).
export type FieldError = { loc: (string | number)[]; msg: string };

export type CreateOrderResult =
  | { kind: "ok"; orderId: string }
  | { kind: "invalid"; errors: FieldError[] }
  | { kind: "modelNotReady" }
  | { kind: "unreachable" };

export async function createOrder(input: NewOrder): Promise<CreateOrderResult> {
  let response: Response;
  try {
    response = await apiFetch(`${BACKEND_URL}/orders`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
  } catch {
    return { kind: "unreachable" };
  }
  if (response.status === 422) {
    const { detail } = (await response.json()) as { detail: FieldError[] };
    return { kind: "invalid", errors: detail };
  }
  if (response.status === 503) {
    return { kind: "modelNotReady" };
  }
  if (!response.ok) {
    return { kind: "unreachable" };
  }
  const { order_id } = (await response.json()) as { order_id: string };
  return { kind: "ok", orderId: order_id };
}

// Bỏ phần tử "body" đầu loc rồi ghép phần còn lại bằng "." làm khoá tra cứu
// ("items.0.seller_id", "customer_state", "payments.1"). Trường lá tra đúng khoá của nó;
// mỗi thẻ dòng sản phẩm/thanh toán tự kiểm khoá bằng đúng chỉ số của nó (không có phần
// trường con, ví dụ "payments.1") để hiện banner đầu dòng đó. Lỗi còn lại sau khi bỏ
// "body" mà thành chuỗi rỗng (loc == ["body"]) rơi vào formLevel.
export function mapFieldErrors(errors: FieldError[]): {
  byPath: Record<string, string>;
  formLevel: string[];
} {
  const byPath: Record<string, string> = {};
  const formLevel: string[] = [];
  for (const error of errors) {
    const path = error.loc
      .slice(error.loc[0] === "body" ? 1 : 0)
      .join(".");
    if (path === "") {
      formLevel.push(error.msg);
    } else {
      byPath[path] = error.msg;
    }
  }
  return { byPath, formLevel };
}
