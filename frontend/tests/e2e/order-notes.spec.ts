import { test, expect, type Page, type Request } from "@playwright/test";

import { mockSession } from "./session";

// Trình duyệt gọi thẳng backend (ADR-0006), nên mẫu chặn phải bám địa chỉ backend chứ
// không phải địa chỉ của trang.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
// `**` vượt cả dấu gạch chéo, nên một mẫu này bắt cả /orders/{id} lẫn /orders/{id}/notes.
// Một handler rẽ nhánh theo đường dẫn.
const ORDERS_API = `${BACKEND_URL}/orders**`;

const ORDER_ID = "e481f51cbdc54678b7cc49136f2d6af7";
const SELLER = "3504c0cb71d7fa48d967e0e4c94d59d9";

// Nhiều sản phẩm để cột nội dung dài hơn hẳn một màn hình — cần cho bài cột dính khi cuộn.
const ORDER = {
  order_id: ORDER_ID,
  order_status: "delivered",
  delivery_outcome: "late",
  order_value: 146.88,
  timeline: {
    purchased_at: "2017-10-02T10:56:33",
    payment_approved_at: "2017-10-02T11:07:15",
    handed_to_carrier_at: "2017-10-04T19:55:00",
    delivered_at: "2017-10-20T21:25:13",
    estimated_delivery_date: "2017-10-18",
    payment_approval_days: 0.0074,
    seller_handling_days: 2.3589,
    carrier_transit_days: 16.0612,
  },
  address: { customer_city: "sao paulo", customer_state: "SP", customer_zip_code_prefix: "03149" },
  items: Array.from({ length: 10 }, (_, index) => ({
    order_item_id: index + 1,
    product_id: `87285b34884572647811a353c7ac49${String(index).padStart(2, "0")}`,
    category: "housewares",
    price: 29.99,
    freight_value: 8.72,
    seller_id: SELLER,
  })),
  sellers: [{ seller_id: SELLER, seller_city: "maua", seller_state: "SP" }],
  payments: [
    { payment_sequential: 1, payment_type: "credit_card", payment_installments: 3, payment_value: 146.88 },
  ],
  reviews: [
    { review_score: 2, comment_title: null, comment_message: "Chegou atrasado.", created_at: "2017-10-21T00:00:00" },
  ],
};

// 08:05 UTC: 15:05 ở Hồ Chí Minh (UTC+7), 05:05 ở São Paulo (UTC-3).
const NEWER_NOTE = {
  id: 2,
  body: "Khách xác nhận đã nhận hàng.\nĐóng khiếu nại.",
  created_at: "2026-09-15T08:05:00Z",
  author: { display_name: "Trần Khoa", role: "logistics_manager" },
};
const OLDER_NOTE = {
  id: 1,
  body: "Đã gọi hãng vận chuyển, hàng kẹt ở kho Campinas.",
  created_at: "2026-09-14T23:40:00Z",
  author: { display_name: "Nguyễn Lan", role: "operations_staff" },
};

type NotesMock = { posts: Request[] };

async function mockOrder(
  page: Page,
  {
    notes = [NEWER_NOTE, OLDER_NOTE],
    postStatus = 201,
  }: { notes?: object[]; postStatus?: number } = {},
): Promise<NotesMock> {
  const mock: NotesMock = { posts: [] };
  await page.route(ORDERS_API, (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname === `/orders/${ORDER_ID}/notes`) {
      if (request.method() === "GET") {
        return route.fulfill({ json: notes });
      }
      mock.posts.push(request);
      if (postStatus !== 201) {
        return route.fulfill({ status: postStatus, json: { detail: "error" } });
      }
      const { body } = request.postDataJSON() as { body: string };
      return route.fulfill({
        status: 201,
        json: {
          id: 3,
          body: body.trim(),
          created_at: "2026-09-15T09:30:00Z",
          author: { display_name: "Nguyễn Lan", role: "operations_staff" },
        },
      });
    }
    if (url.pathname === `/orders/${ORDER_ID}`) {
      return route.fulfill({ json: ORDER });
    }
    return route.fulfill({ status: 404, json: { detail: "Order not found" } });
  });
  return mock;
}

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" }]);
  await mockSession(context);
});

test.describe("múi giờ Hồ Chí Minh", () => {
  test.use({ timezoneId: "Asia/Ho_Chi_Minh" });

  test("mở đơn thì thấy mọi ghi chú, mới nhất trên cùng, kèm tên, vai trò và thời điểm", async ({
    page,
  }) => {
    await mockOrder(page);
    await page.goto(`/orders/${ORDER_ID}`);

    const notes = page.getByTestId("order-note");
    await expect(notes).toHaveCount(2);
    await expect(notes.nth(0).getByTestId("order-note-body")).toHaveText(NEWER_NOTE.body);
    await expect(notes.nth(0).getByTestId("order-note-byline")).toHaveText(
      "Trần Khoa · Quản lý hậu cần · 15:05 15/09/2026",
    );
    await expect(notes.nth(1).getByTestId("order-note-byline")).toHaveText(
      "Nguyễn Lan · Nhân viên vận hành · 06:40 15/09/2026",
    );
    await expect(page.getByTestId("order-notes")).toContainText(
      "Ghi chú không sửa hay xóa được. Ghi nhầm thì thêm một ghi chú đính chính.",
    );
  });
});

test.describe("múi giờ São Paulo", () => {
  test.use({ timezoneId: "America/Sao_Paulo" });

  // Cùng created_at với bài trên mà ra giờ khác: thời điểm theo múi giờ trình duyệt, không
  // theo múi giờ máy chủ Next hay quy ước UTC của dữ liệu Olist. Ghi chú cũ lùi sang hôm trước.
  test("cùng một thời điểm ghi chú hiện theo múi giờ của trình duyệt người xem", async ({
    page,
  }) => {
    await mockOrder(page);
    await page.goto(`/orders/${ORDER_ID}`);

    const notes = page.getByTestId("order-note");
    await expect(notes.nth(0).getByTestId("order-note-byline")).toHaveText(
      "Trần Khoa · Quản lý hậu cần · 05:05 15/09/2026",
    );
    await expect(notes.nth(1).getByTestId("order-note-byline")).toHaveText(
      "Nguyễn Lan · Nhân viên vận hành · 20:40 14/09/2026",
    );
  });
});

test("gửi một ghi chú thì nó hiện ngay trên cùng và ô nhập được xoá", async ({ page }) => {
  const mock = await mockOrder(page);
  await page.goto(`/orders/${ORDER_ID}`);
  await expect(page.getByTestId("order-note")).toHaveCount(2);

  await page.getByTestId("order-notes-input").fill("Hẹn giao lại thứ Hai.");
  await page.getByTestId("order-notes-submit").click();

  const notes = page.getByTestId("order-note");
  await expect(notes).toHaveCount(3);
  await expect(notes.nth(0).getByTestId("order-note-body")).toHaveText("Hẹn giao lại thứ Hai.");
  await expect(notes.nth(0).getByTestId("order-note-byline")).toContainText(
    "Nguyễn Lan · Nhân viên vận hành",
  );
  await expect(notes.nth(1).getByTestId("order-note-body")).toHaveText(NEWER_NOTE.body);
  await expect(page.getByTestId("order-notes-input")).toHaveValue("");
  await expect(page.getByTestId("order-notes-error")).toHaveCount(0);

  expect(mock.posts).toHaveLength(1);
  expect(mock.posts[0].postDataJSON()).toEqual({ body: "Hẹn giao lại thứ Hai." });
  expect(await mock.posts[0].headerValue("authorization")).toBe("Bearer test-access-token");
});

test("đơn chưa có ghi chú thì báo chưa có, gửi ghi chú đầu tiên thì thay chỗ đó", async ({
  page,
}) => {
  await mockOrder(page, { notes: [] });
  await page.goto(`/orders/${ORDER_ID}`);
  await expect(page.getByTestId("order-notes-empty")).toHaveText("Chưa có ghi chú nào.");

  await page.getByTestId("order-notes-input").fill("Ghi chú đầu tiên");
  await page.getByTestId("order-notes-submit").click();

  await expect(page.getByTestId("order-note")).toHaveCount(1);
  await expect(page.getByTestId("order-notes-empty")).toHaveCount(0);
});

test("ghi chú chỉ toàn khoảng trắng hoặc dài quá 2.000 ký tự thì báo lý do và không gửi", async ({
  page,
}) => {
  const mock = await mockOrder(page);
  await page.goto(`/orders/${ORDER_ID}`);
  const input = page.getByTestId("order-notes-input");
  const error = page.getByTestId("order-notes-error");

  await input.fill("   \n  ");
  await page.getByTestId("order-notes-submit").click();
  await expect(error).toHaveText("Ghi chú không được để trống.");

  await input.fill("a".repeat(2001));
  await page.getByTestId("order-notes-submit").click();
  await expect(error).toHaveText("Ghi chú dài 2.001 ký tự, tối đa 2.000.");

  await expect(page.getByTestId("order-note")).toHaveCount(2);
  await expect(input).toHaveValue("a".repeat(2001));
  expect(mock.posts).toHaveLength(0);
});

// 422 là máy chủ từ chối nội dung (lọt qua kiểm ở trình duyệt, ví dụ khoảng trắng mà trim()
// của JS không cắt nhưng strip() của Python cắt) — phải nói lý do, không chỉ mã lỗi.
const SUBMIT_ERRORS = [
  {
    status: 422,
    message:
      "Máy chủ không nhận ghi chú này: nội dung phải dài 1–2.000 ký tự sau khi bỏ khoảng trắng hai đầu.",
  },
  {
    status: 500,
    message: "Không gửi được ghi chú (máy chủ trả về mã 500). Vui lòng thử lại.",
  },
];

for (const { status, message } of SUBMIT_ERRORS) {
  test(`máy chủ trả ${status} thì báo không gửi được và giữ nguyên chữ đã gõ`, async ({ page }) => {
    const mock = await mockOrder(page, { postStatus: status });
    await page.goto(`/orders/${ORDER_ID}`);

    await page.getByTestId("order-notes-input").fill("Ghi chú bị từ chối");
    await page.getByTestId("order-notes-submit").click();

    await expect(page.getByTestId("order-notes-error")).toHaveText(message);
    await expect(page.getByTestId("order-notes-input")).toHaveValue("Ghi chú bị từ chối");
    await expect(page.getByTestId("order-note")).toHaveCount(2);
    expect(mock.posts).toHaveLength(1);
  });
}

test("màn hình rộng: cuộn trang chi tiết dài thì khối ghi chú đứng yên bên phải", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await mockOrder(page);
  await page.goto(`/orders/${ORDER_ID}`);
  await expect(page.getByTestId("order-note")).toHaveCount(2);

  const notes = page.getByTestId("order-notes");
  const timeline = page.getByTestId("order-timeline");
  const scrollTo = async (y: number) => {
    await page.evaluate((top) => window.scrollTo(0, top), y);
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(y);
  };

  const notesAtTop = (await notes.boundingBox())!;
  const timelineAtTop = (await timeline.boundingBox())!;
  // Cột phải, cạnh cột nội dung chứ không nằm dưới nó.
  expect(notesAtTop.x).toBeGreaterThan(timelineAtTop.x + timelineAtTop.width - 1);

  await scrollTo(400);
  const notesFirst = (await notes.boundingBox())!;
  const timelineFirst = (await timeline.boundingBox())!;
  await scrollTo(800);
  const notesSecond = (await notes.boundingBox())!;
  const timelineSecond = (await timeline.boundingBox())!;

  // Nội dung cuộn đi đúng 400px, còn khối ghi chú dính ở mép trên (top-4) và không nhúc nhích.
  expect(timelineFirst.y - timelineSecond.y).toBeCloseTo(400, 0);
  expect(Math.abs(notesSecond.y - notesFirst.y)).toBeLessThan(2);
  expect(notesSecond.y).toBeCloseTo(16, 0);
  expect(notesSecond.x).toBeCloseTo(notesAtTop.x, 0);
});

test("màn hình rộng: ghi chú nhiều hơn một màn hình thì cột dính cuộn riêng, đọc được tới ghi chú cũ nhất", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  const many = Array.from({ length: 30 }, (_, index) => ({
    ...OLDER_NOTE,
    id: 100 - index,
    body: `Ghi chú số ${30 - index}: đã liên hệ hãng vận chuyển và cập nhật tình trạng cho khách.`,
  }));
  await mockOrder(page, { notes: many });
  await page.goto(`/orders/${ORDER_ID}`);
  await expect(page.getByTestId("order-note")).toHaveCount(30);

  await page.evaluate(() => window.scrollTo(0, 400));
  const column = page.getByTestId("order-notes-column");
  const box = (await column.boundingBox())!;
  // Cột không cao quá màn hình, nên không có ghi chú nào chỉ hiện khi cuộn tới cuối trang.
  expect(box.y + box.height).toBeLessThanOrEqual(800);

  const oldest = page.getByTestId("order-note").last();
  await oldest.scrollIntoViewIfNeeded();
  await expect(oldest).toBeInViewport();
  expect(await column.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
});

test("màn hình hẹp: khối ghi chú nằm cuối trang, dưới phần đánh giá, không cuộn ngang", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockOrder(page);
  await page.goto(`/orders/${ORDER_ID}`);
  await expect(page.getByTestId("order-note")).toHaveCount(2);

  const reviews = (await page.getByTestId("order-reviews").boundingBox())!;
  const notes = (await page.getByTestId("order-notes").boundingBox())!;
  expect(notes.y).toBeGreaterThan(reviews.y + reviews.height - 1);
  expect(Math.abs(notes.x - reviews.x)).toBeLessThan(1);

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test("đổi sang tiếng Anh thì mọi nhãn của khối ghi chú đổi theo", async ({ page, context }) => {
  await context.addCookies([{ name: "NEXT_LOCALE", value: "en", url: "http://localhost:3000" }]);
  await mockOrder(page);
  await page.goto(`/orders/${ORDER_ID}`);

  const notes = page.getByTestId("order-notes");
  await expect(notes).toContainText("Internal notes");
  await expect(notes).toContainText(
    "Notes cannot be edited or deleted. To correct one, add a new note.",
  );
  await expect(page.getByTestId("order-notes-input")).toHaveAttribute(
    "placeholder",
    "Record how this order was handled…",
  );
  await expect(page.getByTestId("order-notes-submit")).toHaveText("Add note");
  await expect(page.getByTestId("order-note").nth(0).getByTestId("order-note-byline")).toContainText(
    "Trần Khoa · Logistics Manager",
  );

  await page.getByTestId("order-notes-input").fill("a".repeat(2001));
  await page.getByTestId("order-notes-submit").click();
  await expect(page.getByTestId("order-notes-error")).toHaveText(
    "The note is 2,001 characters long; the limit is 2,000.",
  );
  await page.getByTestId("order-notes-input").fill(" ");
  await page.getByTestId("order-notes-submit").click();
  await expect(page.getByTestId("order-notes-error")).toHaveText("The note cannot be empty.");
});
