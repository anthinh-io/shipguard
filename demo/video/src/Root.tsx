import { AbsoluteFill, Composition, Sequence } from "remotion";

import { ClipView, type ClipPlan } from "./ClipView";
import audioSec from "./data/audio-durations.json";
import chon from "./data/chon.json";
import clipSec from "./data/clips.json";
import fit from "./data/fit.json";
import motion from "./data/motion.json";
import narration from "./data/narration.json";
import { FPS, planClips } from "./lib/timeline.mjs";

type PlannedClip = ClipPlan & { id: string; canh: number };

const plan = planClips(narration, clipSec, audioSec, chon, fit, motion) as { clips: PlannedClip[]; frames: number };

// Một composition gồm các clip đã chọn, nối tiếp nhau kể từ khung hình 0.
function makeComposition(clips: PlannedClip[]) {
  const base = clips[0].offset;
  const frames = clips.reduce((n, c) => n + c.frames, 0);
  const Comp: React.FC = () => (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      {clips.map((c) => (
        <Sequence key={c.id} from={c.offset - base} durationInFrames={Math.max(1, c.frames)} name={c.clip}>
          <ClipView plan={c} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
  return { Comp, frames };
}

const canhs = [...new Set(plan.clips.map((c) => c.canh))];

export const Root: React.FC = () => (
  <>
    {canhs.map((n) => {
      const { Comp, frames } = makeComposition(plan.clips.filter((c) => c.canh === n));
      return <Composition key={n} id={`Canh${n}`} component={Comp} durationInFrames={frames} fps={FPS} width={1920} height={1080} />;
    })}
    {(() => {
      const { Comp, frames } = makeComposition(plan.clips);
      return <Composition id="Full" component={Comp} durationInFrames={frames} fps={FPS} width={1920} height={1080} />;
    })()}
  </>
);
