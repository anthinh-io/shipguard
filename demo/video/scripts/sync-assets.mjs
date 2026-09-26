// Chép các đoạn video đã quay (demo/clips) sang public/clips để Remotion đọc bằng staticFile, và ghi thời
// lượng từng đoạn vào src/data/clips.json.
import { execFileSync } from "node:child_process";
import { copyFileSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
// Mặc định đọc demo/clips (nơi recording/ ghi ra); đổi bằng biến môi trường DEMO_CLIPS_DIR.
const src = process.env.DEMO_CLIPS_DIR || path.join(root, "..", "clips");
const dest = path.join(root, "public", "clips");
mkdirSync(dest, { recursive: true });

const durations = {};
for (const f of readdirSync(src).filter((f) => f.endsWith(".webm") || f.endsWith(".mp4"))) {
  copyFileSync(path.join(src, f), path.join(dest, f));
  const out = execFileSync(
    process.platform === "win32" ? "npx.cmd" : "npx",
    ["remotion", "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", "public/clips/" + f],
    { cwd: root, encoding: "utf8", shell: process.platform === "win32" },
  );
  durations[f] = Number(out.trim());
  console.log("chép", f, durations[f].toFixed(2) + "s");
}
writeFileSync(path.join(root, "src/data/clips.json"), JSON.stringify(durations, null, 2) + "\n");
