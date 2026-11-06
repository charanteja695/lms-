import { useMemo } from "react";

import { proctoringSessionStorage } from "@/core/lib/storage";
import { useProctorBrowserEvents } from "@/modules/assessments/attempts/hooks/proctoring/useProctorBrowserEvents";
import { useProctorEventQueue } from "@/modules/assessments/attempts/hooks/proctoring/useProctorEventQueue";
import { useProctorHeartbeat } from "@/modules/assessments/attempts/hooks/proctoring/useProctorHeartbeat";
import { useProctorAudio } from "@/modules/assessments/attempts/hooks/proctoring/useProctorAudio";
import { useProctorRecording } from "@/modules/assessments/attempts/hooks/proctoring/useProctorRecording";
import { useProctorScreen } from "@/modules/assessments/attempts/hooks/proctoring/useProctorScreen";
import { useProctorSnapshots } from "@/modules/assessments/attempts/hooks/proctoring/useProctorSnapshots";
import type { ProctoringLevel } from "@/modules/assessments/common/types";

/**
 * Runs the client side of a proctored attempt while it is in progress: fullscreen enforcement,
 * the browser events docs/API.md lists, heartbeats (which carry staff directives back), and for
 * strict tests, a live camera with periodic snapshot uploads, microphone clips, the continuous recording, and (if the test requires it) the shared screen. A no-op for "none" or when the
 * pre-check was never completed (nothing in sessionStorage for this attempt to report against).
 */
export function useExamProctoring(attemptId: string, level: ProctoringLevel, active: boolean) {
  const ref = useMemo(() => proctoringSessionStorage.read(attemptId), [attemptId]);
  const sessionId = active && ref ? ref.sessionId : null;
  const strict = level === "strict";

  const { queueEvent } = useProctorEventQueue(sessionId);
  const { warning, resume } = useProctorBrowserEvents(Boolean(sessionId), queueEvent);
  const { snapshotIntervalSeconds } = useProctorHeartbeat(sessionId, ref?.heartbeatIntervalSeconds ?? 15);
  const interval = snapshotIntervalSeconds || ref?.snapshotIntervalSeconds || 25;
  const { videoRef, ready, getStream } = useProctorSnapshots(sessionId, strict, interval, queueEvent);
  useProctorAudio(strict ? sessionId : null, ref?.audioIntervalSeconds ?? 0, ref?.audioClipSeconds ?? 0, getStream, ready);
  const screen = useProctorScreen(sessionId, strict && Boolean(ref?.screenShare), interval, queueEvent);
  const flushRecording = useProctorRecording(strict ? sessionId : null, ref?.videoChunkSeconds ?? 0, getStream, ready);

  return { recording: strict && Boolean(sessionId) && ready, videoRef, screen, flushRecording, warning, resume };
}
