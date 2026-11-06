import { useCallback, useEffect, useRef } from "react";

import { useProctorUpload } from "@/modules/assessments/attempts/hooks/proctoring/useProctorUpload";

const TYPES = ["video/webm;codecs=vp8,opus", "video/webm", "video/mp4"];
const FLUSH_TIMEOUT_MS = 10_000;

function supportedType(): string | null {
  if (typeof MediaRecorder === "undefined") return null;
  return TYPES.find((type) => MediaRecorder.isTypeSupported(type)) ?? null;
}

/**
 * Strict: records the whole attempt from the exam's own camera and microphone. The recorder restarts every
 * `chunkSeconds`, so each uploaded piece is a complete, playable file a reviewer can open on its own. `flush()` ends the
 * current piece and waits for its upload: call it before submitting, so the recording is saved with the attempt.
 */
export function useProctorRecording(sessionId: string | null, chunkSeconds: number, getStream: () => MediaStream | null, cameraReady: boolean) {
  const upload = useProctorUpload(sessionId);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const pendingRef = useRef<Promise<void>>(Promise.resolve());
  const stoppedRef = useRef(false);

  const startPiece = useCallback(() => {
    const type = supportedType();
    const stream = getStream();
    if (!type || !stream || stoppedRef.current) return;
    const tracks = stream.getTracks().filter((track) => track.readyState === "live");
    if (tracks.length === 0) return;
    const chunks: Blob[] = [];
    const recorder = new MediaRecorder(new MediaStream(tracks), { mimeType: type, videoBitsPerSecond: 350_000 });
    const contentType = type.split(";")[0] ?? "video/webm";
    recorder.ondataavailable = (event) => event.data.size > 0 && chunks.push(event.data);
    recorder.onstop = () => {
      if (chunks.length === 0) return;
      const piece = upload("video", new Blob(chunks, { type: contentType }), contentType, contentType === "video/mp4" ? "piece.mp4" : "piece.webm");
      pendingRef.current = pendingRef.current.then(() => piece);
    };
    recorder.start();
    recorderRef.current = recorder;
  }, [getStream, upload]);

  useEffect(() => {
    if (!sessionId || !cameraReady || chunkSeconds <= 0) return;
    stoppedRef.current = false;
    startPiece();
    const timer = window.setInterval(() => {
      if (recorderRef.current?.state === "recording") recorderRef.current.stop(); // its onstop uploads the piece
      startPiece();
    }, chunkSeconds * 1000);
    return () => {
      window.clearInterval(timer);
      stoppedRef.current = true;
      if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    };
  }, [sessionId, cameraReady, chunkSeconds, startPiece]);

  return useCallback(async () => {
    stoppedRef.current = true;
    const recorder = recorderRef.current;
    if (recorder?.state === "recording") {
      await new Promise<void>((resolve) => {
        recorder.addEventListener("stop", () => resolve(), { once: true });
        recorder.stop();
      });
    }
    // wait for the last pieces, but never hold the submit hostage to a slow network
    await Promise.race([pendingRef.current, new Promise((resolve) => window.setTimeout(resolve, FLUSH_TIMEOUT_MS))]);
  }, []);
}
