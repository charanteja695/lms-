import { useCallback, useRef, useState } from "react";

import { useAppSelector } from "@/app/hooks";
import { toApiError } from "@/core/lib/apiError";
import { useCreateItemMutation, useDeleteItemMutation } from "@/modules/catalog/courses/api/curriculumApi";
import { uploadMediaMultipart } from "@/modules/media/api/uploadMediaMultipart";

export type UploadKind = "video" | "pdf";
export type UploadState = "uploading" | "processing" | "ready" | "failed" | "cancelled";

export interface LessonUpload {
  id: string;
  kind: UploadKind;
  fileName: string;
  sizeLabel: string;
  title: string;
  percent: number;
  state: UploadState;
  error?: string;
}

export interface TopicRef {
  courseId: string;
  versionId: string;
  moduleId: string;
  topicId: string;
}

export const ACCEPT: Record<UploadKind, string> = {
  video: "video/mp4,video/quicktime,video/webm,video/x-matroska",
  pdf: "application/pdf",
};

const sizeLabel = (bytes: number) =>
  bytes >= 1024 * 1024 * 1024
    ? `${(bytes / 1024 ** 3).toFixed(1)} GB`
    : bytes >= 1024 * 1024
    ? `${Math.round(bytes / 1024 ** 2)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;

const titleFrom = (name: string) =>
  name
    .replace(/\.[^.]+$/, "")
    .replace(/[-_]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 200) || "Lesson";

/**
 * Turns dropped files into lessons using direct multipart upload to media-service.
 */
export function useLessonUploads(topic: TopicRef) {
  const [uploads, setUploads] = useState<LessonUpload[]>([]);
  const aborts = useRef(new Map<string, () => void>());
  const token = useAppSelector((state) => state.auth.accessToken);
  const [createItem] = useCreateItemMutation();
  const [deleteItem] = useDeleteItemMutation();

  const patch = useCallback(
    (id: string, changes: Partial<LessonUpload>) =>
      setUploads((list) => list.map((u) => (u.id === id ? { ...u, ...changes } : u))),
    []
  );

  const start = useCallback(
    async (file: File, kind: UploadKind) => {
      const id = crypto.randomUUID();
      const title = titleFrom(file.name);
      setUploads((list) => [
        ...list,
        {
          id,
          kind,
          fileName: file.name,
          sizeLabel: sizeLabel(file.size),
          title,
          percent: 0,
          state: "uploading",
        },
      ]);
      let itemId: string | null = null;
      try {
        const result = await uploadMediaMultipart(
          {
            file,
            kind,
            title,
            courseId: topic.courseId,
            moduleId: topic.moduleId,
            topicId: topic.topicId,
            token,
            onProgress: (percent) => patch(id, { percent }),
          },
          (abortFn) => aborts.current.set(id, abortFn)
        );
        patch(id, { percent: 100, state: "processing" });
        const item = await createItem({
          ...topic,
          body: {
            item_type: kind,
            title,
            media_id: result.asset_id,
          },
        }).unwrap();
        itemId = item.topic_item_id;
        patch(id, { percent: 100, state: "ready" });
      } catch (error) {
        const cancelled =
          (error instanceof DOMException && error.name === "AbortError") ||
          (error instanceof Error && error.message.toLowerCase().includes("cancelled"));
        if (itemId) {
          await deleteItem({ ...topic, topicItemId: itemId })
            .unwrap()
            .catch(() => undefined);
        }
        patch(id, cancelled ? { state: "cancelled" } : { state: "failed", error: error instanceof Error ? error.message : toApiError(error).message });
      } finally {
        aborts.current.delete(id);
      }
    },
    [createItem, deleteItem, patch, token, topic]
  );

  const addFiles = useCallback(
    (files: File[], kind: UploadKind) => files.forEach((file) => void start(file, kind)),
    [start]
  );
  const cancel = useCallback((id: string) => aborts.current.get(id)?.(), []);
  const dismiss = useCallback(
    (id: string) => setUploads((list) => list.filter((u) => u.id !== id)),
    []
  );
  const busy = uploads.some((u) => u.state === "uploading");

  return { uploads, addFiles, cancel, dismiss, busy };
}
