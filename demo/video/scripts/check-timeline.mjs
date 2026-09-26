// In bảng thời gian từng đoạn và kiểm tra: đủ tệp âm thanh, lời đọc khớp nguyên văn kich-ban-demo.md,
// không đoạn nào phải giữ hình quá lâu hay video dài hơn lời đọc quá nhiều, tổng độ dài hợp lý.
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { FPS, PAD, planClips } from "../src/lib/timeline.mjs";
import { readScriptTexts } from "./script-md.mjs";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const load = (p) => JSON.parse(readFileSync(path.join(root, p), "utf8"));
const narration = load("src/data/narration.json");
const clipSec = load("src/data/clips.json");
const audioSec = load("src/data/audio-durations.json");
const chon = load("src/data/chon.json");
const fit = load("src/data/fit.json");
const motion = load("src/data/motion.json");

const MAX_HOLD = 8; // giây
const MAX_EXTRA = 5; // giây video được dài hơn lời đọc trước khi cảnh báo
const errors = [];
const warns = [];

const scriptTexts = new Set(readScriptTexts());
for (const c of narration) {
  for (const q of c.cues) {
    if (!scriptTexts.has(q.text)) errors.push(`${q.id}: text không có nguyên văn trong kich-ban-demo.md`);
  }
}

const plan = planClips(narration, clipSec, audioSec, chon, fit, motion);
const mmss = (frames) => {
  const total = Math.round(frames / FPS);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
};
const f1 = (frames) => (frames / FPS).toFixed(1);

const perCanh = {};
for (const c of plan.clips) {
  console.log(`\n${c.clip}  (clip ${clipSec[c.clip].toFixed(1)}s, trong video từ ${mmss(c.offset)}, dài ${mmss(c.frames)})`);
  console.log(`  câu          mốc  video  thao tác  lời đọc     ra  tốc độ  thừa  bỏ đuôi  chế độ (mặc định: ${fit.mode})`);
  for (const s of c.segments) {
    const hold = s.hold / FPS;
    const extra = (s.len - Math.ceil((s.audioSec + PAD) * FPS)) / FPS; // video dài hơn lời đọc
    const flag = !s.audio ? "  THIẾU ÂM THANH" : hold > MAX_HOLD ? "  giữ hình lâu" : extra > MAX_EXTRA ? "  video dài hơn lời" : "";
    console.log(
      `  ${s.cue.id.padEnd(11)} ${String(s.cue.t).padStart(4)}s ${f1(s.gap).padStart(5)}s ${f1(s.active).padStart(7)}s ${s.audioSec.toFixed(1).padStart(7)}s ${f1(s.len).padStart(5)}s ${s.rate.toFixed(2).padStart(5)}x ${extra.toFixed(1).padStart(5)}s ${f1(s.gap - s.used).padStart(6)}s  ${s.mode}${flag}`,
    );
    if (!s.audio) errors.push(`${s.cue.id}: thiếu tệp âm thanh`);
    else if (hold > MAX_HOLD) warns.push(`${s.cue.id}: phải giữ hình ${hold.toFixed(1)}s`);
    else if (extra > MAX_EXTRA) warns.push(`${s.cue.id}: video dài hơn lời đọc ${extra.toFixed(1)}s`);
    if (s.gap === 0 && s.cue.t >= clipSec[c.clip]) errors.push(`${s.cue.id}: mốc ${s.cue.t}s nằm ngoài clip`);
    const t = (perCanh[c.canh] ??= { before: 0, after: 0, voice: 0 });
    t.before += s.gap;
    t.after += s.len;
    t.voice += s.audioSec * FPS;
  }
}

console.log("\nTheo cảnh (giây):  cảnh   video gốc   video sau   lời đọc   chênh");
for (const [n, t] of Object.entries(perCanh)) {
  console.log(`                   ${n.padStart(4)}   ${f1(t.before).padStart(9)}   ${f1(t.after).padStart(9)}   ${f1(t.voice).padStart(7)}   ${f1(t.after - t.voice).padStart(5)}`);
}

const totalMin = plan.frames / FPS / 60;
console.log(`\nTổng độ dài: ${mmss(plan.frames)} (${totalMin.toFixed(1)} phút)`);
if (totalMin > 25) warns.push(`tổng độ dài ${totalMin.toFixed(1)} phút, gần giới hạn 30 phút của đồ án`);
for (const w of warns) console.log("Cảnh báo:", w);
for (const e of errors) console.log("LỖI:", e);
process.exit(errors.length ? 1 : 0);
