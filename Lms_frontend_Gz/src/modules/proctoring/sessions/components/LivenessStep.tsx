import { useEffect, useState } from "react";

import { useCameraCapture } from "@/core/hooks/useCameraCapture";
import { useNotify } from "@/core/hooks/useNotify";
import { cn } from "@/core/lib/cn";
import { uploadToPresignedPost } from "@/core/lib/presignedUpload";
import type { LivenessPose } from "@/modules/proctoring/common/types";
import { useGetProctorSnapshotUploadUrlMutation, useRegisterProctorSnapshotMutation } from "@/modules/proctoring/sessions/api/sessionsApi";
import { Alert, Button, Card, Icon, type IconName } from "@/shared/ui";

const PROMPTS: Record<LivenessPose, { say: string; arrow: IconName; rotate: string }> = {
  left: { say: "Turn your head to the left", arrow: "chevronLeft", rotate: "" },
  right: { say: "Turn your head to the right", arrow: "chevronRight", rotate: "" },
  up: { say: "Look up", arrow: "chevronLeft", rotate: "rotate-90" },
  down: { say: "Look down", arrow: "chevronLeft", rotate: "-rotate-90" },
};
const COUNTDOWN = 3;

/**
 * Face movements: the student turns their head each way on request; one frame per pose is uploaded and kept with the
 * attempt for a person to review. The camera keeps running; each pose gets a short countdown so the head is turned.
 */
export function LivenessStep({ sessionId, poses, onContinue }: { sessionId: string; poses: LivenessPose[]; onContinue: () => void }) {
  const notify = useNotify();
  const camera = useCameraCapture();
  const [getUploadUrl] = useGetProctorSnapshotUploadUrlMutation();
  const [registerSnapshot] = useRegisterProctorSnapshotMutation();
  const [index, setIndex] = useState(0);
  const [count, setCount] = useState<number | null>(null);
  const [failed, setFailed] = useState(false);
  const pose = poses[index];
  const done = index >= poses.length;

  useEffect(() => {
    void camera.start();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (count === null || !pose) return;
    if (count > 0) {
      const timer = window.setTimeout(() => setCount(count - 1), 1000);
      return () => window.clearTimeout(timer);
    }
    void (async () => {
      try {
        const blob = await camera.capture();
        if (!blob) throw new Error("The camera gave no picture");
        const target = await getUploadUrl({ sessionId, kind: "liveness", contentType: "image/jpeg", pose }).unwrap();
        await uploadToPresignedPost(target.upload, blob, `${pose}.jpg`);
        await registerSnapshot({ sessionId, kind: "liveness", key: target.key }).unwrap();
        setIndex((i) => i + 1);
        setCount(index + 1 < poses.length ? COUNTDOWN : null); // straight on to the next pose
      } catch (error) {
        setFailed(true);
        setCount(null);
        notify.apiError(error);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [count]);

  const begin = () => {
    setFailed(false);
    setCount(COUNTDOWN);
  };

  return (
    <Card title="Face movements" description="This proves a real person is taking the test. Keep your face inside the oval.">
      <div className="space-y-5">
        {camera.error && <Alert tone="error">{camera.error}</Alert>}
        <div className="relative mx-auto aspect-[4/3] w-full max-w-md overflow-hidden rounded-2xl bg-navy-950">
          <video ref={camera.videoRef} muted playsInline className="h-full w-full -scale-x-100 object-cover" />
          <div className={cn("pointer-events-none absolute left-1/2 top-1/2 h-[72%] w-[46%] -translate-x-1/2 -translate-y-1/2 rounded-[50%] border-4 transition-colors", done ? "border-brand-400" : count !== null ? "border-accent-400" : "border-white/70")} />
          {pose && count !== null && (
            <div className="absolute inset-x-0 bottom-0 flex items-center justify-center gap-3 bg-gradient-to-t from-navy-950/90 to-transparent px-4 pb-4 pt-10 text-white">
              <Icon name={PROMPTS[pose].arrow} size={28} className={PROMPTS[pose].rotate} />
              <span className="text-lg font-bold">{PROMPTS[pose].say}</span>
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-white/15 text-lg font-bold tabular-nums">{count || "•"}</span>
            </div>
          )}
          {done && (
            <div className="absolute inset-0 flex items-center justify-center bg-brand-900/40">
              <span className="flex items-center gap-2 rounded-full bg-white px-4 py-2 font-bold text-brand-700"><Icon name="check" size={18} /> All done</span>
            </div>
          )}
        </div>

        <ol className="flex justify-center gap-2" aria-label="Poses">
          {poses.map((p, i) => (
            <li key={p} className={cn("rounded-full px-3 py-1 text-xs font-semibold capitalize ring-1", i < index ? "bg-brand-50 text-brand-700 ring-brand-200" : i === index && count !== null ? "bg-accent-50 text-accent-700 ring-accent-200" : "bg-white text-slate-500 ring-slate-200")}>
              {i < index && "✓ "}
              {p}
            </li>
          ))}
        </ol>

        {failed && <Alert tone="error">That pose did not save. Check your connection and try again.</Alert>}
        <div className="flex justify-end gap-2">
          {!done && (
            <Button disabled={!camera.ready || count !== null} onClick={begin}>
              {index === 0 ? "Start face check" : "Try again"}
            </Button>
          )}
          {done && <Button onClick={onContinue}>Continue</Button>}
        </div>
      </div>
    </Card>
  );
}
