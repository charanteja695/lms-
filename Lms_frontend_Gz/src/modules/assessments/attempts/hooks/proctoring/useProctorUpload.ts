import { useCallback } from "react";

import { uploadToPresignedPost } from "@/core/lib/presignedUpload";
import { useGetExamSnapshotUploadUrlMutation, useRegisterExamSnapshotMutation } from "@/modules/assessments/attempts/api/proctoringClientApi";

export type CaptureKind = "periodic" | "screen" | "audio" | "video";

/** Uploads one capture straight to storage and registers it with the session. A failure is swallowed: the next interval tries again. */
export function useProctorUpload(sessionId: string | null) {
  const [getUploadUrl] = useGetExamSnapshotUploadUrlMutation();
  const [registerSnapshot] = useRegisterExamSnapshotMutation();

  return useCallback(
    async (kind: CaptureKind, blob: Blob, contentType: string, filename: string) => {
      if (!sessionId) return;
      try {
        const target = await getUploadUrl({ sessionId, kind, contentType }).unwrap();
        await uploadToPresignedPost(target.upload, blob, filename);
        await registerSnapshot({ sessionId, kind, key: target.key }).unwrap();
      } catch {
        /* a missed capture is not fatal */
      }
    },
    [sessionId, getUploadUrl, registerSnapshot],
  );
}
