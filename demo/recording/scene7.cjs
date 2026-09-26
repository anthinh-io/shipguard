// Cảnh 7: kết (0:45).
const { runScene, cardHtml } = require("./lib.cjs");

runScene("canh-7-ket", {}, async (s) => {
  await s.page.setContent(
    cardHtml({
      title: "Tóm tắt",
      lines: [
        "Chạy cả hệ thống bằng một lệnh: docker compose up -d --build --wait",
        "Nhân viên vận hành: bảng điều khiển, tra cứu đơn, tạo đơn, ghi nhận xử lý và mốc, ghi chú, hủy đơn",
        "Quản lý hậu cần: chỉ số mô hình và đối chiếu trên đơn thật",
        "Super Admin: tài khoản và phân quyền theo vai trò",
        "Giới hạn: F1 ở mốc đặt hàng 19,72%, chưa đạt mục tiêu 30%; bảng đối chiếu mới có 12 đơn chuẩn bị sẵn",
      ],
      footer: "Cảm ơn thầy đã xem",
    }),
  );
  await s.syncTo(45);
});
