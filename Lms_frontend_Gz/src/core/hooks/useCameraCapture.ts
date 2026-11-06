import { useCallback, useEffect, useRef, useState } from "react";

/** Opens the camera (and mic) and lets the caller grab a JPEG frame from it. Used by proctoring's pre-check photos and the exam player's periodic snapshots. */
export function useCameraCapture(onTrackEnded?: (kind: "video" | "audio") => void) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [ready, setReady] = useState(false);
  const [hasAudio, setHasAudio] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: true });
      streamRef.current = stream;
      stream.getTracks().forEach((track) => {
        track.addEventListener("ended", () => onTrackEnded?.(track.kind === "audio" ? "audio" : "video"));
      });
      setHasAudio(stream.getAudioTracks().length > 0);
      setReady(true);
    } catch {
      setError("Camera and microphone access was denied or is unavailable.");
      setReady(false);
    }
  }, [onTrackEnded]);

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setReady(false);
  }, []);

  useEffect(() => () => stop(), [stop]);

  // The preview <video> is often rendered only once the camera is ready, so attach the stream after that render.
  useEffect(() => {
    const video = videoRef.current;
    if (!ready || !video || !streamRef.current || video.srcObject === streamRef.current) return;
    video.srcObject = streamRef.current;
    void video.play().catch(() => undefined);
  });

  const capture = useCallback(async (): Promise<Blob | null> => {
    const video = videoRef.current;
    if (!video || !ready || video.videoWidth === 0) return null; // no frame yet
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0);
    return new Promise((resolve) => canvas.toBlob((blob) => resolve(blob), "image/jpeg", 0.9));
  }, [ready]);

  /** The live camera + microphone stream (the exam player records short microphone clips from it). */
  const getStream = useCallback(() => streamRef.current, []);

  return { videoRef, ready, hasAudio, error, start, stop, capture, getStream };
}
