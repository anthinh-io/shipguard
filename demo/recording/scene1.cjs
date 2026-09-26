// Cảnh 1: mở đầu. Ba đoạn: thẻ tiêu đề, ảnh tĩnh docker compose ps (phương án thay thế cho đoạn
// terminal tự quay bằng Game Bar) và trang đăng nhập.
const { execSync } = require("node:child_process");
const { runScene, cardHtml, BASE } = require("./lib.cjs");

// Thư mục Source đang chạy dự án shipverify (nơi có docker-compose.yml, .env và db/initdb), truyền qua biến môi trường.
const COMPOSE_DIR = process.env.SHIPGUARD_SOURCE_DIR;
if (!COMPOSE_DIR) {
  console.error("Chưa đặt biến môi trường SHIPGUARD_SOURCE_DIR (thư mục Source đang chạy shipverify).");
  process.exit(1);
}

(async () => {
  await runScene("canh-1a-tieu-de", {}, async (s) => {
    await s.page.setContent(
      cardHtml({
        title: "ShipGuard",
        lines: [
          "Ứng dụng quản lý và dự đoán hiệu suất giao hàng bằng học máy",
          "Sinh viên: Nguyễn Thanh Thịnh · MSSV 22730096",
          "Giảng viên: ThS. Mai Xuân Hùng",
        ],
        footer: "Video Demo",
      }),
    );
    await s.syncTo(20);
  });

  // Ảnh tĩnh từ kết quả docker compose ps thật lúc chạy.
  let ps = "";
  try {
    ps = execSync('docker compose -p shipverify ps --format "table {{.Service}}	{{.Status}}	{{.Ports}}"', { cwd: COMPOSE_DIR, encoding: "utf8" });
  } catch (e) {
    ps = String(e.stdout || e.message);
  }
  await runScene("canh-1-terminal-tinh", {}, async (s) => {
    await s.page.setContent(
      cardHtml({
        title: "docker compose up -d --build --wait",
        lines: ["$ docker compose ps", ps.replace(/&/g, "&amp;").replace(/</g, "&lt;")],
        mono: true,
      }),
    );
    await s.syncTo(30);
  });

  await runScene("canh-1b-dang-nhap", {}, async (s) => {
    await s.goto("/login");
    await s.page.getByTestId("login-form").waitFor();
    await s.moveTo("login-email");
    await s.syncTo(25);
  });
})();
