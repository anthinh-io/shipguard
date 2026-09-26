// Tạo âm thanh thuyết minh bằng Edge TTS (giọng vi-VN-NamMinhNeural), không cần khóa API.
//   node scripts/tts.mjs            tạo câu còn thiếu (bỏ qua tệp đã có)
//   node scripts/tts.mjs --force    tạo lại tất cả
//   node scripts/tts.mjs canh-3-6   chỉ tạo các câu có id bắt đầu bằng "canh-3-6" (kèm --force nếu đã có)
//   --voice vi-VN-HoaiMyNeural      đổi giọng (tệp ra thêm hậu tố .hoaimy)
// Câu có bản phiên âm (tts) được tạo hai bản: <id>.mp3 (phiên âm) và <id>.raw.mp3 (nguyên văn) để nghe so.
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { MsEdgeTTS, OUTPUT_FORMAT } from "msedge-tts";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const audioDir = path.join(root, "public", "audio");
mkdirSync(audioDir, { recursive: true });

const args = process.argv.slice(2);
const force = args.includes("--force");
const voiceIdx = args.indexOf("--voice");
const voice = voiceIdx >= 0 ? args[voiceIdx + 1] : "vi-VN-NamMinhNeural";
const suffix = voiceIdx >= 0 ? `.${voice.split("-")[2].replace("Neural", "").toLowerCase()}` : "";
const filters = args.filter((a, i) => !a.startsWith("--") && i !== voiceIdx + 1);

const escapeXml = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

async function synth(text, file) {
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const tts = new MsEdgeTTS();
      await tts.setMetadata(voice, OUTPUT_FORMAT.AUDIO_24KHZ_48KBITRATE_MONO_MP3);
      const { audioStream } = tts.toStream(escapeXml(text));
      const chunks = [];
      await new Promise((resolve, reject) => {
        audioStream.on("data", (c) => chunks.push(c));
        audioStream.on("close", resolve);
        audioStream.on("error", reject);
      });
      const buf = Buffer.concat(chunks);
      if (buf.length < 2000) throw new Error(`âm thanh quá ngắn (${buf.length} byte)`);
      writeFileSync(file, buf);
      return;
    } catch (e) {
      if (attempt === 3) throw e;
      console.log(`  thử lại (${attempt}): ${e.message}`);
      await new Promise((r) => setTimeout(r, 1500 * attempt));
    }
  }
}

const narration = JSON.parse(readFileSync(path.join(root, "src/data/narration.json"), "utf8"));
const cues = narration.flatMap((c) => c.cues).filter((q) => !filters.length || filters.some((f) => q.id.startsWith(f)));

for (const q of cues) {
  const jobs = [{ file: `${q.id}${suffix}.mp3`, text: q.tts ?? q.text }];
  if (q.tts) jobs.push({ file: `${q.id}.raw${suffix}.mp3`, text: q.text });
  for (const j of jobs) {
    const dest = path.join(audioDir, j.file);
    if (existsSync(dest) && !force) continue;
    await synth(j.text, dest);
    console.log("tạo", j.file);
  }
}

// Thời lượng từng tệp: mp3 tốc độ bit cố định 48 kbit/s nên giây = byte * 8 / 48000.
const durations = {};
for (const f of readdirSync(audioDir).filter((f) => f.endsWith(".mp3"))) {
  durations[f] = Math.round(((statSync(path.join(audioDir, f)).size * 8) / 48000) * 1000) / 1000;
}
writeFileSync(path.join(root, "src/data/audio-durations.json"), JSON.stringify(durations, null, 2) + "\n");
console.log(`Xong: ${Object.keys(durations).length} tệp âm thanh.`);
