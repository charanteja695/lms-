import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { uploadToPresignedPost } from "@/core/lib/presignedUpload";
import { useGetAttachmentUploadUrlMutation } from "@/modules/support/common/api/attachmentsApi";
import type { AttachmentRef } from "@/modules/support/common/types";

export interface PendingAttachment {
  id: string;
  filename: string;
  size: number;
  ref: AttachmentRef | null; // set once the upload has finished
}

/** Files picked for one message: each goes straight to storage as soon as it is picked; the message sends only the refs. */
export function useAttachmentUploads() {
  const notify = useNotify();
  const [getUploadUrl] = useGetAttachmentUploadUrlMutation();
  const [items, setItems] = useState<PendingAttachment[]>([]);

  const uploadOne = async (file: File) => {
    const id = crypto.randomUUID();
    setItems((current) => [...current, { id, filename: file.name, size: file.size, ref: null }]);
    try {
      const contentType = file.type || "application/octet-stream";
      const { key, upload } = await getUploadUrl({ filename: file.name, content_type: contentType, size_bytes: file.size }).unwrap();
      await uploadToPresignedPost(upload, file, file.name);
      setItems((current) => current.map((item) => (item.id === id ? { ...item, ref: { key, filename: file.name } } : item)));
    } catch (error) {
      setItems((current) => current.filter((item) => item.id !== id));
      notify.apiError(error);
    }
  };

  return {
    items,
    add: (files: FileList | null) => Array.from(files ?? []).forEach((file) => void uploadOne(file)),
    remove: (id: string) => setItems((current) => current.filter((item) => item.id !== id)),
    reset: () => setItems([]),
    uploading: items.some((item) => item.ref === null),
    refs: items.flatMap((item) => (item.ref ? [item.ref] : [])),
  };
}
