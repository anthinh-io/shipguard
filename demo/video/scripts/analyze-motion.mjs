// Đo chuyển động của từng clip: trích khung ở 5 khung/giây, so hai khung liên tiếp, ghi kết quả
// vào src/data/motion.json: mỗi phần tử là số điểm ảnh (khung 640x360) đổi mạnh so với mẫu trước.
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { PNG } from "pngjs";

export const MOTION_FPS = 5;
const CHANGE = 40; // ngưỡng lệch của một điểm ảnh (thang 0 đến 255)
const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const tmp = path.join(root, ".motion-tmp");
const cli = path.join(root, "node_modules", "@remotion", "cli", "remotion-cli.js");

const motion = {};
for (const clip of readdirSync(path.join(root, "public", "clips")).filter((f) => f.endsWith(".webm") || f.endsWith(".mp4"))) {
  rmSync(tmp, { recursive: true, force: true });
  mkdirSync(tmp, { recursive: true });
  execFileSync(
    process.execPath,
    [cli, "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", `public/clips/${clip}`, "-r", String(MOTION_FPS), "-s", "640x360", ".motion-tmp/f_%05d.png"],
    { cwd: root },
  );
  const files = readdirSync(tmp).filter((f) => f.endsWith(".png")).sort();
  const series = [0];
  let prev = PNG.sync.read(readFileSync(path.join(tmp, files[0]))).data;
  for (let i = 1; i < files.length; i++) {
    const cur = PNG.sync.read(readFileSync(path.join(tmp, files[i]))).data;
    // Đếm số điểm ảnh đổi mạnh (lệch quá ${CHANGE} ở một kênh màu): chữ hiện ra hay con trỏ đi đều làm tăng số
    // này, còn nhiễu nén (đổi nhẹ trên toàn khung, mỗi khoảng 5 giây một lần) thì không.
    let count = 0;
    for (let p = 0; p < cur.length; p += 4) {
      if (Math.abs(cur[p] - prev[p]) > CHANGE || Math.abs(cur[p + 1] - prev[p + 1]) > CHANGE || Math.abs(cur[p + 2] - prev[p + 2]) > CHANGE) count++;
    }
    series.push(count);
    prev = cur;
  }
  motion[clip] = series;
  console.log(clip, files.length, "khung");
}
rmSync(tmp, { recursive: true, force: true });
writeFileSync(path.join(root, "src/data/motion.json"), JSON.stringify(motion) + "\n");
