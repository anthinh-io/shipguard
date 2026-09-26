// Tính thời gian cho từng đoạn của video: hàm thuần, dùng chung cho Remotion (src/) và scripts/check-timeline.mjs.
//
// Mỗi clip có danh sách mốc (cue): giây trong clip mà một câu thuyết minh bắt đầu. Clip được cắt thành các
// đoạn giữa hai mốc liền nhau (đoạn cuối chạy tới hết clip). "khoảng trống" (gap) là độ dài đoạn video gốc,
// "cần" (need) là thời lượng lời đọc + PAD. Cách khớp khi lời đọc và video khác nhau (fit.json):
//   keep  video giữ nguyên; lời ngắn hơn thì im lặng phần còn lại, lời dài hơn thì giữ khung hình cuối.
//   cut   lời ngắn hơn thì cắt bỏ phần đuôi của đoạn video, chỉ giữ phần đầu vừa đủ lời đọc.
//   speed lời ngắn hơn thì tăng tốc đoạn video cho vừa lời đọc, tối đa maxSpeed lần; cần nhanh hơn nữa
//         thì cắt bỏ phần đuôi còn dư, nên video luôn dài đúng bằng lời đọc.
//   smart  chỉ cắt thời gian chờ (màn hình đứng yên, đo ở motion.json); phần có thao tác giữ nguyên, nếu
//          dài hơn lời đọc thì tăng tốc tối đa maxSpeed lần (không cắt thao tác).
//   slack (giây) là độ dài video được phép vượt lời đọc trước khi cắt/tăng tốc (0 = khít với lời đọc).
// Lời đọc dài hơn video thì mọi chế độ đều giữ khung hình cuối cho đủ lời.

export const FPS = 25;
export const PAD = 0.4; // giây nghỉ sau khi đọc xong
export const LEAD = 0.2; // giây audio bắt đầu chậm sau mốc

/** @param {{id:string}} cue @param {Record<string,number>} audioSec @param {Record<string,string>} chon */
export function audioFileFor(cue, audioSec, chon = {}) {
  const raw = `${cue.id}.raw.mp3`;
  return chon[cue.id] === "raw" && audioSec[raw] != null ? raw : `${cue.id}.mp3`;
}

const DEFAULT_FIT = { mode: "keep", maxSpeed: 2, slack: 0, overrides: {} };
export const MOTION_FPS = 5; // tốc độ lấy mẫu của motion.json

/**
 * Số khung hình (từ đầu đoạn) có thao tác: tới mẫu cuối cùng có chuyển động vượt ngưỡng, cộng tailPad giây.
 * series[i] là độ khác giữa mẫu i và mẫu i-1 (mẫu i ở giây i / MOTION_FPS).
 */
export function activeFrames(series, from, gap, fit, fps = FPS) {
  const thr = fit.motionThreshold ?? 15;
  const pad = Math.round((fit.tailPad ?? 0.8) * fps);
  if (!series) return gap;
  const i0 = Math.floor((from / fps) * MOTION_FPS);
  const i1 = Math.min(series.length - 1, Math.ceil(((from + gap) / fps) * MOTION_FPS));
  let last = -1;
  for (let i = i0 + 1; i <= i1; i++) if (series[i] > thr) last = i;
  const doneAt = last < 0 ? from : Math.round((last / MOTION_FPS) * fps);
  return Math.max(pad, Math.min(gap, doneAt - from + pad));
}

/**
 * @param {{clip:string, cues:{id:string,t:number}[]}} clipDef
 * @param {number} clipSec thời lượng clip (giây)
 * @param {Record<string,number>} audioSec thời lượng tệp âm thanh theo tên tệp
 * @param {Record<string,string>} chon câu nào dùng bản nguyên văn ("raw")
 * @param {{mode:string,maxSpeed:number,overrides:Record<string,string>}} fit
 */
export function planClip(clipDef, clipSec, audioSec, chon = {}, fit = DEFAULT_FIT, motion = {}, fps = FPS) {
  const clipFrames = Math.floor(clipSec * fps);
  const segments = [];
  let start = 0;
  clipDef.cues.forEach((cue, i) => {
    const from = Math.round(cue.t * fps);
    const to = i + 1 < clipDef.cues.length ? Math.round(clipDef.cues[i + 1].t * fps) : clipFrames;
    const gap = Math.max(0, Math.min(to, clipFrames) - from); // số khung hình video gốc của đoạn
    const audio = audioFileFor(cue, audioSec, chon);
    const sec = audioSec[audio] ?? 0;
    const need = sec ? Math.ceil((sec + PAD) * fps) : 0;
    const target = need ? need + Math.round((fit.slack ?? 0) * fps) : 0; // độ dài mong muốn của phần video
    const ov = fit.overrides?.[cue.id]; // "keep" | "cut" | "speed" | "smart" hoặc { mode, maxSpeed }
    const mode = (typeof ov === "string" ? ov : ov?.mode) ?? fit.mode ?? "keep";
    const maxSpeed = (typeof ov === "object" ? ov?.maxSpeed : undefined) ?? fit.maxSpeed ?? 2;

    let active = gap; // số khung hình đầu của đoạn có thao tác (chỉ tính ở chế độ smart)
    let play = gap; // số khung hình đầu ra dành cho phần video chạy
    let used = gap; // số khung hình video gốc được dùng
    let rate = 1;
    if (target > 0 && target < gap && mode === "smart") {
      active = activeFrames(motion[clipDef.clip], from, gap, fit, fps);
      if (active <= target) {
        play = target;
        used = target;
      } else {
        rate = Math.min(active / target, maxSpeed);
        used = active;
        play = Math.ceil(active / rate);
      }
    } else if (target > 0 && target < gap && mode === "cut") {
      play = target;
      used = target;
    } else if (target > 0 && target < gap && mode === "speed") {
      rate = Math.min(gap / target, maxSpeed);
      play = target;
      used = Math.min(gap, Math.round(target * rate));
    }
    const len = Math.max(play, need);
    const hold = len - play; // giữ khung hình cuối của phần video đã dùng
    segments.push({
      cue, audio: sec ? audio : null, audioSec: sec, mode, from, gap, active, used, play, rate, hold, len, start,
    });
    start += len;
  });
  return { clip: clipDef.clip, frames: start, segments };
}

/** Kế hoạch cho một danh sách clip nối tiếp nhau. */
export function planClips(clipDefs, clipDurations, audioSec, chon = {}, fit = DEFAULT_FIT, motion = {}, fps = FPS) {
  let offset = 0;
  const clips = clipDefs.map((def) => {
    const plan = planClip(def, clipDurations[def.clip], audioSec, chon, fit, motion, fps);
    const out = { ...plan, id: def.id, canh: def.canh, offset };
    offset += plan.frames;
    return out;
  });
  return { clips, frames: offset };
}
