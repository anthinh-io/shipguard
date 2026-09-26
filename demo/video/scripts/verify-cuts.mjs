// Kiểm tra độc lập phần đuôi bị cắt: với mỗi đoạn bị cắt, so khung hình ngay trước điểm cắt với khung hình
// ở cuối đoạn video gốc. Hai khung giống nhau (độ khác trung bình nhỏ) nghĩa là phần bị bỏ chỉ là thời gian chờ.
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { PNG } from "pngjs";

import { FPS, planClips } from "../src/lib/timeline.mjs";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const load = (p) => JSON.parse(readFileSync(path.join(root, p), "utf8"));
const plan = planClips(load("src/data/narration.json"), load("src/data/clips.json"), load("src/data/audio-durations.json"), load("src/data/chon.json"), load("src/data/fit.json"), load("src/data/motion.json"));
const cli = path.join(root, "node_modules", "@remotion", "cli", "remotion-cli.js");
const tmp = path.join(root, ".verify-tmp");
rmSync(tmp, { recursive: true, force: true });
mkdirSync(tmp, { recursive: true });

function frame(clip, sec, name) {
  const out = `.verify-tmp/${name}.png`;
  execFileSync(process.execPath, [cli, "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", sec.toFixed(2), "-i", `public/clips/${clip}`, "-frames:v", "1", "-s", "480x270", out], { cwd: root });
  return PNG.sync.read(readFileSync(path.join(root, out))).data;
}
const meanDiff = (a, b) => {
  let s = 0;
  for (let i = 0; i < a.length; i += 4) s += Math.abs(a[i] - b[i]) + Math.abs(a[i + 1] - b[i + 1]) + Math.abs(a[i + 2] - b[i + 2]);
  return s / (a.length / 4) / 3;
};

const LIMIT = 0.5; // độ khác trung bình (thang 0 đến 255) coi là có thay đổi thật
let bad = 0;
console.log("câu          bỏ đuôi   từ (s) → đến (s)   độ khác");
for (const c of plan.clips) {
  for (const s of c.segments) {
    const cutFrames = s.gap - s.used;
    if (cutFrames < FPS / 2) continue;
    const t1 = (s.from + s.used - 1) / FPS;
    const t2 = (s.from + s.gap - 1) / FPS;
    const d = meanDiff(frame(c.clip, t1, "a"), frame(c.clip, t2, "b"));
    const flag = d > LIMIT ? "  <-- CÓ THAY ĐỔI Ở PHẦN BỊ CẮT" : "";
    if (d > LIMIT) bad++;
    console.log(`${s.cue.id.padEnd(11)} ${(cutFrames / FPS).toFixed(1).padStart(6)}s   ${t1.toFixed(1).padStart(6)} → ${t2.toFixed(1).padStart(6)}      ${d.toFixed(3)}${flag}`);
  }
}
rmSync(tmp, { recursive: true, force: true });
console.log(bad ? `\n${bad} đoạn bị cắt mất thay đổi.` : "\nKhông đoạn nào bị cắt mất thay đổi.");
process.exit(bad ? 1 : 0);
