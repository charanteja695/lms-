import { useCallback, useRef, useState } from "react";

/** Records a spoken answer with the browser's MediaRecorder; the server transcribes it (or answers SPEECH_UNAVAILABLE). */
export function useVoiceAnswer() {
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const media = new MediaRecorder(stream);
      chunks.current = [];
      media.ondataavailable = (event) => chunks.current.push(event.data);
      media.start();
      recorder.current = media;
      setRecording(true);
    } catch {
      setError("Microphone access was denied — type your answer instead.");
    }
  }, []);

  const stop = useCallback(
    () =>
      new Promise<Blob | null>((resolve) => {
        const media = recorder.current;
        if (!media) return resolve(null);
        media.onstop = () => {
          media.stream.getTracks().forEach((track) => track.stop());
          setRecording(false);
          resolve(new Blob(chunks.current, { type: media.mimeType || "audio/webm" }));
        };
        media.stop();
      }),
    [],
  );

  return { recording, error, start, stop };
}
