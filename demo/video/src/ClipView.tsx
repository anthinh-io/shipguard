// Dựng một clip: mỗi đoạn (giữa hai mốc) là một Sequence gồm phần video chạy, phần giữ hình khi lời đọc dài
// hơn thao tác, và audio thuyết minh. Audio đặt ngang hàng với Freeze (audio bên trong Freeze bị tắt tiếng).
import { AbsoluteFill, Freeze, Sequence, staticFile } from "remotion";
import { Audio, Video } from "@remotion/media";

import { FPS, LEAD } from "./lib/timeline.mjs";

type Segment = {
  cue: { id: string };
  audio: string | null;
  from: number;
  used: number;
  play: number;
  rate: number;
  hold: number;
  len: number;
  start: number;
};
export type ClipPlan = { clip: string; frames: number; offset: number; segments: Segment[] };

const videoStyle = { width: "100%", height: "100%", objectFit: "fill" } as const;

export const ClipView: React.FC<{ plan: ClipPlan }> = ({ plan }) => {
  const src = staticFile(`clips/${plan.clip}`);
  return (
    <AbsoluteFill>
      {plan.segments
        .filter((s) => s.len > 0)
        .map((s) => (
          <Sequence key={s.cue.id} from={s.start} durationInFrames={s.len} name={s.cue.id}>
            {s.play > 0 && (
              <Sequence durationInFrames={s.play} layout="none">
                <Video src={src} trimBefore={s.from} playbackRate={s.rate} muted style={videoStyle} />
              </Sequence>
            )}
            {s.hold > 0 && s.play > 0 && (
              <Sequence from={s.play} durationInFrames={s.hold} layout="none">
                <Freeze frame={0}>
                  <Video src={src} trimBefore={s.from + s.used - 1} muted style={videoStyle} />
                </Freeze>
              </Sequence>
            )}
            {s.audio && (
              <Sequence from={Math.round(LEAD * FPS)} layout="none">
                <Audio src={staticFile(`audio/${s.audio}`)} />
              </Sequence>
            )}
          </Sequence>
        ))}
    </AbsoluteFill>
  );
};
