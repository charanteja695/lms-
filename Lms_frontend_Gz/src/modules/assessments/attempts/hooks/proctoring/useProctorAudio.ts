import { useEffect } from "react";

import { useProctorUpload } from "@/modules/assessments/attempts/hooks/proctoring/useProctorUpload";

const MIME = "audio/webm";

/** Strict: every `intervalSeconds`, record `clipSeconds` from the exam's own microphone and upload it for the voice check. */
export function useProctorAudio(sessionId: string | null, intervalSeconds: number, clipSeconds: number, getStream: () => MediaStream | null, cameraReady: boolean) {
  const upload = useProctorUpload(sessionId);

  useEffect(() => {
    if (!sessionId || !cameraReady || intervalSeconds <= 0 || clipSeconds <= 0) return;
    if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported(MIME)) return; // this browser cannot record webm audio
    let recorder: MediaRecorder | null = null;
    const record = () => {
      const audio = getStream()?.getAudioTracks().filter((track) => track.readyState === "live") ?? [];
      if (audio.length === 0 || recorder?.state === "recording") return;
      const chunks: Blob[] = [];
      recorder = new MediaRecorder(new MediaStream(audio), { mimeType: MIME });
      recorder.ondataavailable = (event) => event.data.size > 0 && chunks.push(event.data);
      recorder.onstop = () => chunks.length > 0 && void upload("audio", new Blob(chunks, { type: MIME }), MIME, "clip.webm");
      recorder.start();
      window.setTimeout(() => recorder?.state === "recording" && recorder.stop(), clipSeconds * 1000);
    };
    const timer = window.setInterval(record, intervalSeconds * 1000);
    return () => {
      window.clearInterval(timer);
      if (recorder?.state === "recording") recorder.stop();
    };
  }, [sessionId, cameraReady, intervalSeconds, clipSeconds, getStream, upload]);
}
