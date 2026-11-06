import { useEffect, useRef, useState } from "react";

import { screenShare } from "@/core/lib/screenShare";
import { Alert, Badge, Button, Card } from "@/shared/ui";

/** This test watches the whole screen: the student shares it now and keeps sharing until they submit. */
export function ScreenShareStep({ onContinue }: { onContinue: (shared: boolean) => void }) {
  const preview = useRef<HTMLVideoElement | null>(null);
  const [stream, setStream] = useState<MediaStream | null>(() => screenShare.get());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (preview.current) preview.current.srcObject = stream;
  }, [stream]);

  const share = async () => {
    setError(null);
    try {
      setStream(await screenShare.request());
    } catch (cause) {
      setError(cause instanceof Error && cause.name !== "NotAllowedError" ? cause.message : "Screen sharing was cancelled. Share your entire screen to continue.");
    }
  };

  return (
    <Card title="Share your screen">
      <div className="space-y-4">
        <p className="text-sm text-slate-600">
          This test needs to see your <strong>entire screen</strong> for as long as it runs. When your browser asks, pick the whole screen —
          not a window or a tab — and keep sharing until you submit. Stopping is reported to the exam team.
        </p>
        {error && <Alert tone="error">{error}</Alert>}
        {stream ? (
          <div className="space-y-3">
            <Badge tone="green">Your screen is shared</Badge>
            <video ref={preview} autoPlay muted playsInline className="aspect-video w-full max-w-md rounded-lg border border-slate-200 bg-slate-900" />
          </div>
        ) : (
          <Button icon="monitor" onClick={() => void share()}>
            Share entire screen
          </Button>
        )}
        <div className="flex justify-end">
          <Button disabled={!stream} onClick={() => onContinue(Boolean(stream))}>
            Continue
          </Button>
        </div>
      </div>
    </Card>
  );
}
