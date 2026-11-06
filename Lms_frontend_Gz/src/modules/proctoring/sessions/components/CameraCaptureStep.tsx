import { useState } from "react";

import { useCameraCapture } from "@/core/hooks/useCameraCapture";
import { useNotify } from "@/core/hooks/useNotify";
import { uploadToPresignedPost } from "@/core/lib/presignedUpload";
import { useGetProctorSnapshotUploadUrlMutation, useRegisterProctorSnapshotMutation } from "@/modules/proctoring/sessions/api/sessionsApi";
import { Alert, Badge, Button, Card } from "@/shared/ui";

type Shot = "id_photo" | "face_enrol";

export function CameraCaptureStep({ sessionId, onContinue }: { sessionId: string; onContinue: (result: { camera: boolean; microphone: boolean }) => void }) {
  const notify = useNotify();
  const camera = useCameraCapture();
  const [getUploadUrl] = useGetProctorSnapshotUploadUrlMutation();
  const [registerSnapshot] = useRegisterProctorSnapshotMutation();
  const [captured, setCaptured] = useState<Record<Shot, boolean>>({ id_photo: false, face_enrol: false });
  const [capturing, setCapturing] = useState<Shot | null>(null);

  const takeShot = async (kind: Shot) => {
    setCapturing(kind);
    try {
      const blob = await camera.capture();
      if (!blob) throw new Error("Capture failed");
      const target = await getUploadUrl({ sessionId, kind }).unwrap();
      await uploadToPresignedPost(target.upload, blob, `${kind}.jpg`);
      await registerSnapshot({ sessionId, kind, key: target.key }).unwrap();
      setCaptured((prev) => ({ ...prev, [kind]: true }));
      notify.success(kind === "id_photo" ? "ID photo captured" : "Face photo captured");
    } catch (error) {
      notify.apiError(error);
    } finally {
      setCapturing(null);
    }
  };

  return (
    <Card title="Camera and microphone check">
      <div className="space-y-4">
        {camera.error && <Alert tone="error">{camera.error}</Alert>}
        {!camera.ready && !camera.error && (
          <Button onClick={() => void camera.start()}>Enable camera and microphone</Button>
        )}
        {camera.ready && (
          <>
            <div className="flex items-center gap-4">
              <video ref={camera.videoRef} muted playsInline className="h-36 w-48 rounded-lg border border-slate-200 bg-black object-cover" />
              <Badge tone={camera.hasAudio ? "green" : "red"}>{camera.hasAudio ? "Microphone detected" : "No microphone"}</Badge>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button variant="secondary" loading={capturing === "id_photo"} onClick={() => void takeShot("id_photo")}>
                {captured.id_photo ? "Retake ID photo" : "Capture ID photo"}
              </Button>
              <Button variant="secondary" loading={capturing === "face_enrol"} onClick={() => void takeShot("face_enrol")}>
                {captured.face_enrol ? "Retake face photo" : "Capture face photo"}
              </Button>
            </div>
          </>
        )}
        <div className="flex justify-end">
          <Button
            disabled={!camera.ready || !captured.id_photo || !captured.face_enrol}
            onClick={() => onContinue({ camera: camera.ready, microphone: camera.hasAudio })}
          >
            Continue
          </Button>
        </div>
      </div>
    </Card>
  );
}
