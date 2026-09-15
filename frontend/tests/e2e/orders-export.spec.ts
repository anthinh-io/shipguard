import { readFileSync } from "node:fs";

import { test, expect, type Page, type Request } from "@playwright/test";

import { mockSession } from "./session";

// Trình duyệt gọi thẳng backend (ADR-0002), nên mẫu chặn phải bám địa chỉ backend chứ
// không phải địa chỉ của trang.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
// `**` vượt cả dấu gạch chéo, nên một mẫu này bắt cả /orders lẫn /orders/export. Một
// handler rẽ nhánh theo đường dẫn, để file xuất không bị trả nhầm JSON của danh sách.
const ORDERS_API = `${BACKEND_URL}/orders**`;

const LIST_QUERY = "delivery_outcome=late&customer_state=SP&sort=order_value&page=3";

const CSV =
  "﻿order_id,order_status,delivery_outcome,purchased_at,estimated_delivery_date," +
  "delivered_at,customer_state,order_value\r\n" +
  "e481f51cbdc54678b7cc49136f2d6af7,delivered,late,2017-10-02T10:56:33,2017-10-18," +
  "2017-10-20T21:25:13,SP,146.88\r\n";

test.beforeEach(async ({ context }) => {
  await context.addCookies([
    { name: "NEXT_LOCALE", value: "vi", url: "http://localhost:3000" },
  ]);
  await mockSession(context);
  await context.route(`${BACKEND_URL}/customer-states`, (route) =>
    route.fulfill({ json: ["RJ", "SP"] }),
  );
});

async function mockOrders(page: Page, exportStatus = 200): Promise<Request[]> {
  const exportRequests: Request[] = [];
  await page.route(ORDERS_API, (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/orders/export") {
      exportRequests.push(route.request());
      return exportStatus === 200
        ? route.fulfill({ body: CSV, contentType: "text/csv; charset=utf-8" })
        : route.fulfill({ status: exportStatus });
    }
    return route.fulfill({
      json: {
        items: [
          {
            order_id: "e481f51cbdc54678b7cc49136f2d6af7",
            order_status: "delivered",
            delivery_outcome: "late",
            purchased_at: "2017-10-02T10:56:33",
            estimated_delivery_date: "2017-10-18",
            delivered_at: "2017-10-20T21:25:13",
            customer_state: "SP",
            order_value: 146.88,
          },
        ],
        total: 6534,
        page: Number(url.searchParams.get("page") ?? "1"),
        page_size: 50,
      },
    });
  });
  return exportRequests;
}

test("bấm Xuất CSV thì tải orders.csv theo đúng bộ lọc và thứ tự, không kèm trang", async ({
  page,
}) => {
  const exportRequests = await mockOrders(page);

  await page.goto(`/orders?${LIST_QUERY}`);
  await expect(page.getByTestId("order-row")).toHaveCount(1);

  const download = page.waitForEvent("download");
  await page.getByTestId("orders-export").click();

  const file = await download;
  expect(file.suggestedFilename()).toBe("orders.csv");
  // Blob giữ nguyên từng byte, kể cả BOM đầu file.
  expect(readFileSync(await file.path(), "utf8")).toBe(CSV);
  expect(exportRequests).toHaveLength(1);
  const request = exportRequests[0];
  expect(Object.fromEntries(new URL(request.url()).searchParams)).toEqual({
    delivery_outcome: "late",
    customer_state: "SP",
    sort: "order_value",
  });
  expect(await request.headerValue("authorization")).toBe("Bearer test-access-token");
  await expect(page.getByTestId("orders-export")).toHaveText("Xuất CSV");
  await expect(page.getByTestId("orders-export")).toBeEnabled();
  await expect(page.getByTestId("orders-export-error")).toHaveCount(0);
});

test("máy chủ lỗi khi xuất thì báo lỗi, danh sách vẫn còn", async ({ page }) => {
  await mockOrders(page, 500);

  await page.goto(`/orders?${LIST_QUERY}`);
  await expect(page.getByTestId("order-row")).toHaveCount(1);
  await page.getByTestId("orders-export").click();

  await expect(page.getByTestId("orders-export-error")).toContainText(
    "Không xuất được file (máy chủ trả về mã 500)",
  );
  await expect(page.getByTestId("order-row")).toHaveCount(1);
  await expect(page.getByTestId("orders-export")).toBeEnabled();
});
