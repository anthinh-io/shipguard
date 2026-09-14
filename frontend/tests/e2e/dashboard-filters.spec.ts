import { test, expect } from "@playwright/test";

import {
  EMPTY_FILTERS,
  parseDashboardFilters,
  toDashboardQuery,
} from "../../app/lib/dashboard-filters";

// Không mở trình duyệt: đường liên kết gửi cho đồng nghiệp ai cũng sửa tay được, và đây
// là chốt duy nhất biến chuỗi truy vấn tuỳ ý thành bộ lọc hợp lệ trước khi gọi backend.
const SELLER_ID = "6560211a19b47992c3666cc44a7e94c0";

function parse(query: string) {
  return parseDashboardFilters(Object.fromEntries(new URLSearchParams(query)));
}

test("không có tham số nào thì không bộ lọc nào, và không ghi gì lên URL", () => {
  expect(parseDashboardFilters({})).toEqual(EMPTY_FILTERS);
  expect(toDashboardQuery(EMPTY_FILTERS)).toBe("");
});

test("đủ bốn bộ lọc đọc ra rồi ghi lại đúng chuỗi ban đầu", () => {
  const query = `start_date=2018-01-01&end_date=2018-01-30&customer_state=SP&seller_id=${SELLER_ID}&comparison=previous`;
  const filters = parse(query);
  expect(filters).toEqual({
    range: { from: "2018-01-01", to: "2018-01-30" },
    customerState: "SP",
    sellerId: SELLER_ID,
    comparison: "previous",
  });
  // Cùng thứ tự với lời gọi /dashboard, nên chuỗi của trang và của máy chủ trùng nhau.
  expect(toDashboardQuery(filters)).toBe(query);
});

test("thiếu một đầu khoảng thời gian thì bỏ cả khoảng", () => {
  expect(parse("start_date=2018-01-01").range).toBeNull();
  expect(parse("end_date=2018-01-30").range).toBeNull();
});

test("khoảng ngược chiều hoặc chỉ một ngày thì bỏ cả khoảng, như lịch không cho chọn", () => {
  expect(parse("start_date=2018-01-30&end_date=2018-01-01").range).toBeNull();
  expect(parse("start_date=2018-01-01&end_date=2018-01-01").range).toBeNull();
  expect(parse("start_date=2018-01-01&end_date=2018-01-02").range).toEqual({
    from: "2018-01-01",
    to: "2018-01-02",
  });
});

test("ngày không có thật hoặc sai định dạng thì bỏ cả khoảng", () => {
  for (const bad of ["2018-02-31", "2018-13-01", "01/02/2018", "abc", ""]) {
    expect(
      parseDashboardFilters({ start_date: bad, end_date: "2018-03-01" }).range,
    ).toBeNull();
  }
});

test("chế độ so sánh lạ thì coi như không so sánh", () => {
  for (const bad of ["none", "yoy", ""]) {
    expect(parseDashboardFilters({ comparison: bad }).comparison).toBeNull();
  }
  expect(parseDashboardFilters({ comparison: "year_over_year" }).comparison).toBe(
    "year_over_year",
  );
});

test("bang và người bán rỗng thì coi như không lọc", () => {
  expect(parse("customer_state=&seller_id=")).toEqual(EMPTY_FILTERS);
});

test("tham số lặp lại thì lấy giá trị đầu", () => {
  expect(
    parseDashboardFilters({ customer_state: ["SP", "RJ"], comparison: ["previous", "x"] }),
  ).toMatchObject({ customerState: "SP", comparison: "previous" });
});
