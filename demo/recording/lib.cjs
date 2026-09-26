// Hàm dùng chung cho các cảnh quay Demo. Playwright chạy ở chế độ thư viện, không qua test runner.
const fs = require("node:fs");
const path = require("node:path");

const PW = path.join(__dirname, "..", "..", "frontend", "node_modules", "@playwright", "test");
const { chromium } = require(PW);

const BASE = process.env.APP_URL || "http://localhost:3000";
const CLIPS = path.join(__dirname, "..", "clips");
const TMP = path.join(__dirname, "..", "clips", "_tmp");
const STATE_FILE = path.join(__dirname, "state.json");

// Mật khẩu dùng chung của ba tài khoản thử, đã công khai trong hướng dẫn cài đặt và sử dụng.
const PASSWORD = "ShipGuard@2026";
const ACCOUNTS = {
  admin: "admin@shipguard.local",
  manager: "logistics_manager@shipguard.com",
  staff: "operations_staff@shipguard.com",
};

// Khung 1536x864 (16:9), quay đúng kích thước này; Clipchamp phóng lên 1080p khi xuất. Không dùng
// CSS zoom vì làm lệch vị trí các hộp chọn và menu.
const VIEWPORT = { width: 1536, height: 864 };
const VIDEO_SIZE = VIEWPORT;

const CURSOR_SCRIPT = () => {
  const install = () => {
    if (document.getElementById("demo-cursor")) return;
    const c = document.createElement("div");
    c.id = "demo-cursor";
    c.style.cssText =
      "position:fixed;left:0;top:0;width:26px;height:26px;z-index:2147483647;pointer-events:none;" +
      "transform:translate(-3px,-2px);transition:none;";
    c.innerHTML =
      '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M3 2l7 19 3-8 8-3z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.documentElement.appendChild(c);
    const ring = document.createElement("div");
    ring.style.cssText =
      "position:fixed;left:0;top:0;width:34px;height:34px;margin:-17px 0 0 -17px;border-radius:50%;" +
      "border:3px solid #ef4444;z-index:2147483646;pointer-events:none;opacity:0;";
    document.documentElement.appendChild(ring);
    window.addEventListener(
      "mousemove",
      (e) => {
        c.style.left = e.clientX + "px";
        c.style.top = e.clientY + "px";
      },
      true,
    );
    window.addEventListener(
      "mousedown",
      (e) => {
        ring.style.left = e.clientX + "px";
        ring.style.top = e.clientY + "px";
        ring.animate(
          [
            { opacity: 1, transform: "scale(0.4)" },
            { opacity: 0, transform: "scale(1.6)" },
          ],
          { duration: 450, easing: "ease-out" },
        );
      },
      true,
    );
  };
  if (document.documentElement) install();
  document.addEventListener("DOMContentLoaded", install);
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Ngày (YYYY-MM-DD) tính theo giờ Việt Nam, lệch so với hôm nay n ngày.
function ymd(offsetDays = 0) {
  return new Date(Date.now() + 7 * 3600000 + offsetDays * 86400000).toISOString().slice(0, 10);
}

function readState() {
  try {
    return JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
  } catch {
    return {};
  }
}
function writeState(patch) {
  fs.writeFileSync(STATE_FILE, JSON.stringify({ ...readState(), ...patch }, null, 2));
}

// Đăng nhập không quay (qua trình duyệt riêng) để cảnh quay bắt đầu khi đã có phiên.
async function preLogin(role) {
  const browser = await chromium.launch();
  const context = await browser.newContext({ locale: "vi-VN", timezoneId: "Asia/Ho_Chi_Minh" });
  const page = await context.newPage();
  await page.goto(`${BASE}/login`);
  await page.getByTestId("login-email").fill(ACCOUNTS[role]);
  await page.getByTestId("login-password").fill(PASSWORD);
  await page.getByTestId("login-submit").click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"));
  const state = await context.storageState();
  await browser.close();
  return state;
}

// Mở một cảnh: trả về page đang quay, đồng hồ cảnh và hàm kết thúc (lưu video ra clips/<name>.webm).
async function openScene(name, { storageState } = {}) {
  fs.mkdirSync(TMP, { recursive: true });
  const browser = await chromium.launch({ args: ["--lang=vi-VN"] });
  const context = await browser.newContext({
    viewport: VIEWPORT,
    locale: "vi-VN",
    timezoneId: "Asia/Ho_Chi_Minh",
    storageState,
    recordVideo: { dir: TMP, size: VIDEO_SIZE },
  });
  await context.addCookies([{ name: "NEXT_LOCALE", value: "vi", url: BASE }]);
  await context.addInitScript(CURSOR_SCRIPT);
  const page = await context.newPage();
  const t0 = Date.now();
  const pos = { x: 760, y: 420 };

  const scene = {
    page,
    pos,
    // Chờ tới mốc thời gian (giây) của cảnh, khớp bảng thời gian trong kịch bản.
    async syncTo(sec) {
      const wait = sec * 1000 - (Date.now() - t0);
      if (wait > 0) await sleep(wait);
      else console.log(`  [${name}] trễ ${(-wait / 1000).toFixed(1)}s so với mốc ${sec}s`);
    },
    elapsed: () => (Date.now() - t0) / 1000,
    async goto(url) {
      await page.goto(url.startsWith("http") ? url : BASE + url);
      await page.mouse.move(pos.x, pos.y);
    },
    async moveTo(target, { steps = 28 } = {}) {
      const loc = typeof target === "string" ? page.getByTestId(target) : target;
      await loc.first().scrollIntoViewIfNeeded();
      const box = await loc.first().boundingBox();
      pos.x = box.x + box.width / 2;
      pos.y = box.y + box.height / 2;
      await page.mouse.move(pos.x, pos.y, { steps });
    },
    async click(target, opts) {
      const loc = typeof target === "string" ? page.getByTestId(target) : target;
      await scene.moveTo(loc, opts);
      await sleep(250);
      await loc.first().click();
      await sleep(350);
    },
    async type(target, text, delay = 55) {
      const loc = typeof target === "string" ? page.getByTestId(target) : target;
      await scene.click(loc);
      await loc.first().pressSequentially(text, { delay });
    },
    // Ô ngày/giờ của trình duyệt không gõ từng chữ được, chỉ điền một lần.
    async fill(target, text) {
      const loc = typeof target === "string" ? page.getByTestId(target) : target;
      await scene.moveTo(loc);
      await sleep(250);
      await loc.first().fill(text);
      await sleep(300);
    },
    async pickOption(trigger, optionName) {
      await scene.click(trigger);
      await scene.click(page.getByRole("option", { name: optionName, exact: true }));
    },
    async login(role) {
      await scene.type("login-email", ACCOUNTS[role]);
      await scene.type("login-password", PASSWORD, 40);
      await scene.click("login-submit");
      await page.waitForURL((u) => !u.pathname.startsWith("/login"));
      await page.mouse.move(pos.x, pos.y);
    },
    async logout() {
      await scene.click("user-menu");
      await scene.click("user-menu-logout");
      await page.waitForURL((u) => u.pathname.startsWith("/login"));
      await page.mouse.move(pos.x, pos.y);
    },
    async scrollBy(dy, ms = 800) {
      const steps = 16;
      for (let i = 0; i < steps; i++) {
        await page.mouse.wheel(0, dy / steps);
        await sleep(ms / steps);
      }
    },
    async finish() {
      const video = page.video();
      await context.close();
      const dest = path.join(CLIPS, `${name}.webm`);
      await video.saveAs(dest);
      await browser.close();
      console.log(`[${name}] ${scene.elapsed().toFixed(1)}s -> ${dest}`);
    },
  };
  return scene;
}

// Chạy một hàm cảnh, luôn lưu video kể cả khi có lỗi để xem lại chỗ hỏng.
async function runScene(name, opts, fn) {
  const scene = await openScene(name, opts);
  try {
    await fn(scene);
  } catch (e) {
    console.error(`[${name}] LỖI:`, e.message);
    try {
      await scene.page.screenshot({ path: path.join(TMP, `${name}-loi.png`) });
    } catch {}
    process.exitCode = 1;
  } finally {
    await scene.finish();
  }
}

// Thẻ chữ toàn màn hình (tiêu đề, tóm tắt) dùng cho Cảnh 1 và Cảnh 7.
function cardHtml({ title, lines = [], footer = "", mono = false }) {
  const body = lines.map((l) => `<p>${l}</p>`).join("");
  return `<!doctype html><html lang="vi"><head><meta charset="utf-8"><style>
  html,body{margin:0;height:100%;background:#0f172a;color:#f8fafc;font-family:"Segoe UI",Arial,sans-serif}
  .wrap{height:100%;display:flex;flex-direction:column;justify-content:center;padding:0 140px}
  h1{font-size:54px;line-height:1.2;margin:0 0 36px}
  p{font-size:30px;line-height:1.5;margin:6px 0;color:#cbd5e1;${mono ? "font-family:Consolas,monospace;white-space:pre;font-size:22px;" : ""}}
  .f{margin-top:44px;font-size:26px;color:#94a3b8}
  </style></head><body><div class="wrap"><h1>${title}</h1>${body}<div class="f">${footer}</div></div></body></html>`;
}

module.exports = { BASE, ACCOUNTS, PASSWORD, chromium, sleep, ymd, readState, writeState, preLogin, openScene, runScene, cardHtml };
