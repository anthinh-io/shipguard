// Chuẩn bị dữ liệu cho bảng "Đối chiếu tích lũy trên đơn thật": 12 đơn đặt lùi 40 ngày,
// đã ghi nhận đủ ba mốc. Chạy sau khi dựng lại dữ liệu sạch, trước khi quay Demo.
// Chỉ dùng tài khoản thử công khai (ShipGuard@2026), không đọc .env.
const B = process.env.BACKEND_URL || "http://localhost:8000";
const DAY = 86400000;

async function api(method, path, token, body) {
  const r = await fetch(`${B}${path}`, {
    method,
    headers: { "content-type": "application/json", authorization: `Bearer ${token}` },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  if (!r.ok) throw new Error(`${method} ${path} -> ${r.status} ${text}`);
  return text ? JSON.parse(text) : null;
}

// [ngày giao cam kết tính từ lúc đặt, ngày khách nhận tính từ lúc đặt, nhóm]
const PLAN = [
  [6, 9, "hẹn gấp, trễ"],
  [6, 9, "hẹn gấp, trễ"],
  [6, 10, "hẹn gấp, trễ"],
  [6, 5, "hẹn gấp, kịp"],
  [6, 5, "hẹn gấp, kịp"],
  [25, 12, "hẹn rộng, kịp"],
  [25, 14, "hẹn rộng, kịp"],
  [25, 16, "hẹn rộng, kịp"],
  [25, 18, "hẹn rộng, kịp"],
  [25, 20, "hẹn rộng, kịp"],
  [25, 30, "hẹn rộng, trễ"],
  [25, 32, "hẹn rộng, trễ"],
];

(async () => {
  const login = await fetch(`${B}/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: "operations_staff@shipguard.com", password: "ShipGuard@2026" }),
  });
  const { access_token: token } = await login.json();
  const sellers = await api("GET", "/sellers?q=1f50f920", token);
  const sellerId = sellers[0].seller_id;

  const base = Date.now() - 40 * DAY;
  for (let i = 0; i < PLAN.length; i++) {
    const [estDays, deliverDays, group] = PLAN[i];
    const placed = new Date(base - i * 60000);
    const at = (days) => new Date(placed.getTime() + days * DAY).toISOString();
    const est = new Date(placed.getTime() + estDays * DAY).toISOString().slice(0, 10);
    const created = await api("POST", "/orders", token, {
      purchased_at: placed.toISOString(),
      estimated_delivery_date: est,
      customer_state: "SP",
      customer_city: "sao paulo",
      customer_zip_code_prefix: "01310",
      items: [{ seller_id: sellerId, product_category_name: "moveis_decoracao", product_weight_g: 500, price: 120.5, freight_value: 25.3 }],
      payments: [{ payment_type: "credit_card", payment_installments: 2, payment_value: 145.8 }],
    });
    const id = created.order_id;
    const p0 = created.risk_assessment.late_probability;
    const flag0 = created.risk_assessment.is_high_risk;
    await api("POST", `/orders/${id}/milestones`, token, { milestone: "payment_approved", recorded_at: at(1) });
    await api("POST", `/orders/${id}/milestones`, token, { milestone: "handed_to_carrier", recorded_at: at(3) });
    await api("POST", `/orders/${id}/milestones`, token, { milestone: "delivered_to_customer", recorded_at: at(deliverDays) });
    console.log(`${String(i + 1).padStart(2)} ${group.padEnd(16)} ${id.slice(0, 8)} p=${(p0 * 100).toFixed(1)}% cao=${flag0}`);
  }

  const m = await api("GET", "/model-metrics", token);
  for (const row of m.reconciliation) {
    console.log(row.checkpoint, `total=${row.total} đúng=${row.correct} sai=${row.incorrect} precision=${row.precision} recall=${row.recall}`);
  }
})().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
