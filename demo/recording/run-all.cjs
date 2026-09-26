// Chạy lần lượt các cảnh: node run-all.cjs (tất cả) hoặc node run-all.cjs 3 4 (chỉ cảnh 3 và 4).
const { spawnSync } = require("node:child_process");
const path = require("node:path");

const wanted = process.argv.slice(2).map(Number);
const scenes = wanted.length ? wanted : [1, 2, 3, 4, 5, 6, 7];
for (const n of scenes) {
  console.log(`--- Cảnh ${n} ---`);
  const r = spawnSync(process.execPath, [path.join(__dirname, `scene${n}.cjs`)], { stdio: "inherit" });
  if (r.status !== 0) {
    console.error(`Cảnh ${n} lỗi (mã ${r.status}); dừng.`);
    process.exit(r.status || 1);
  }
}
