import { useCallback, useEffect, useRef, useState } from "react";

import { grabFrame, screenShare } from "@/core/lib/screenShare";
import { useProctorUpload } from "@/modules/assessments/attempts/hooks/proctoring/useProctorUpload";

/**
 * A test that requires screen sharing: a frame of the shared screen goes up every `intervalSeconds`. If sharing stops
 * (the student ends it, or a reload loses it) that is reported once as `screen_share_stopped` and `sharing` turns false,
 * so the player can ask them to share again with `reshare`.
 */
export function useProctorScreen(sessionId: string | null, required: boolean, intervalSeconds: number, queueEvent: (type: string) => void) {
  const upload = useProctorUpload(sessionId);
  const [stream, setStream] = useState<MediaStream | null>(() => screenShare.get());
  const active = Boolean(sessionId) && required;

  useEffect(() => {
    if (!active) return;
    if (!stream) {
      queueEvent("screen_share_stopped");
      return;
    }
    const track = stream.getVideoTracks()[0];
    const ended = () => setStream(null);
    track?.addEventListener("ended", ended);
    return () => track?.removeEventListener("ended", ended);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, stream]);

  useEffect(() => {
    if (!active || !stream) return;
    const timer = window.setInterval(() => {
      void grabFrame(stream).then((blob) => blob && upload("screen", blob, "image/jpeg", "screen.jpg"));
    }, intervalSeconds * 1000);
    return () => window.clearInterval(timer);
  }, [active, stream, intervalSeconds, upload]);

  // The attempt ended (submitted or timed out): stop sharing. Not on unmount, which StrictMode also does on mount.
  const wasActive = useRef(active);
  useEffect(() => {
    if (wasActive.current && !active) screenShare.stop();
    wasActive.current = active;
  }, [active]);

  const reshare = useCallback(async () => {
    try {
      setStream(await screenShare.request());
      return null;
    } catch (cause) {
      return cause instanceof Error && cause.name !== "NotAllowedError" ? cause.message : "Screen sharing was cancelled.";
    }
  }, []);

  return { required: active, sharing: Boolean(stream), reshare };
}
