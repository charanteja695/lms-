import { useEffect } from "react";

import { useCameraCapture } from "@/core/hooks/useCameraCapture";
import { useProctorUpload } from "@/modules/assessments/attempts/hooks/proctoring/useProctorUpload";

/** Strict-only: keeps the camera live and uploads a periodic snapshot every `intervalSeconds` (docs/API.md). */
export function useProctorSnapshots(sessionId: string | null, strict: boolean, intervalSeconds: number, queueEvent: (type: string) => void) {
  const camera = useCameraCapture((kind) => queueEvent(kind === "video" ? "camera_off" : "mic_off"));
  const upload = useProctorUpload(sessionId);

  useEffect(() => {
    if (!strict || !sessionId) return;
    void camera.start();
    return () => camera.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strict, sessionId]);

  useEffect(() => {
    if (!strict || !sessionId || !camera.ready) return;
    const capture = async () => {
      const blob = await camera.capture();
      if (blob) await upload("periodic", blob, "image/jpeg", "periodic.jpg");
    };
    const timer = window.setInterval(() => void capture(), intervalSeconds * 1000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strict, sessionId, camera.ready, intervalSeconds]);

  return { videoRef: camera.videoRef, ready: camera.ready, getStream: camera.getStream };
}
