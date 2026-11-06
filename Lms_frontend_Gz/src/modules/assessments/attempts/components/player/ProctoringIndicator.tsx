import type { RefObject } from "react";

import { Badge } from "@/shared/ui";

/** The live self-view for a strict-proctored attempt; the video element must be mounted before the camera starts. */
export function ProctoringIndicator({ videoRef, recording }: { videoRef: RefObject<HTMLVideoElement | null>; recording: boolean }) {
  return (
    <div className="fixed bottom-4 right-4 z-40 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg">
      <video ref={videoRef} muted playsInline className="h-24 w-32 bg-black object-cover" />
      <div className="px-2 py-1 text-center">
        <Badge tone={recording ? "red" : "gray"}>{recording ? "Recording" : "Camera starting…"}</Badge>
      </div>
    </div>
  );
}
