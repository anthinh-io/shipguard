// Tạo src/data/narration.json: chép nguyên văn lời thuyết minh từ kich-ban-demo.md (theo thứ tự các dòng
// bảng), ghép với mốc trong cues.json, thêm bản phiên âm (tts) theo phien-am.json.
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { readScriptTexts } from "./script-md.mjs";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const cues = JSON.parse(readFileSync(path.join(root, "src/data/cues.json"), "utf8"));
const rules = JSON.parse(readFileSync(path.join(root, "src/data/phien-am.json"), "utf8"));

const texts = readScriptTexts();
const expected = cues.reduce((n, c) => n + c.cues.length, 0);
if (texts.length !== expected) throw new Error(`Kịch bản có ${texts.length} câu, cues.json cần ${expected}.`);

let k = 0;
const out = cues.map((c) => ({
  id: c.id,
  canh: c.canh,
  clip: c.clip,
  cues: c.cues.map((t, i) => {
    const text = texts[k++];
    let tts = text;
    for (const [from, to] of rules) tts = tts.replace(new RegExp(from, "g"), to);
    return { id: `${c.id}-${i + 1}`, t, text, ...(tts !== text ? { tts } : {}) };
  }),
}));

writeFileSync(path.join(root, "src/data/narration.json"), JSON.stringify(out, null, 2) + "\n");
const changed = out.flatMap((c) => c.cues).filter((q) => q.tts).length;
console.log(`narration.json: ${expected} câu, ${changed} câu có bản phiên âm.`);
