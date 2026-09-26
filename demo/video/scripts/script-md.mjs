// Đọc lời thuyết minh từ kich-ban-demo.md: cột thứ ba (trong dấu nháy kép) của mọi dòng bảng có ba cột.
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const SCRIPT_MD = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "kich-ban-demo.md");

export function readScriptTexts() {
  return readFileSync(SCRIPT_MD, "utf8")
    .split(/\r?\n/)
    .map((line) => line.match(/^\|[^|]+\|[^|]+\|\s*"(.+)"\s*\|$/))
    .filter(Boolean)
    .map((m) => m[1]);
}
