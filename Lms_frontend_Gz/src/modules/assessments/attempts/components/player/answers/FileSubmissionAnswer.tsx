import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { uploadToPresignedPost } from "@/core/lib/presignedUpload";
import { useGetFileUploadUrlMutation } from "@/modules/assessments/attempts/api/attemptsApi";
import { Button, FileDropzone, Icon } from "@/shared/ui";

interface UploadedFile {
  key: string;
  filename: string;
  size: number;
  content_type: string;
}

export function FileSubmissionAnswer({ attemptId, questionId, allowedExtensions, maxFiles, maxSizeMb, response, onChange, disabled }: {
  attemptId: string;
  questionId: string;
  allowedExtensions?: string[];
  maxFiles: number;
  maxSizeMb: number;
  response: Record<string, unknown> | null;
  onChange: (response: Record<string, unknown>) => void;
  disabled: boolean;
}) {
  const notify = useNotify();
  const [getUploadUrl, { isLoading: requesting }] = useGetFileUploadUrlMutation();
  const [uploading, setUploading] = useState(false);
  const files = (response?.files as UploadedFile[]) ?? [];
  const accept = allowedExtensions?.length ? allowedExtensions.map((extension) => `.${extension}`).join(",") : undefined;

  const upload = async (file: File) => {
    setUploading(true);
    try {
      const { upload: presigned, key } = await getUploadUrl({ attemptId, questionId, fileName: file.name, contentType: file.type || "application/octet-stream", sizeBytes: file.size }).unwrap();
      await uploadToPresignedPost(presigned, file, file.name);
      onChange({ files: [...files, { key, filename: file.name, size: file.size, content_type: file.type || "application/octet-stream" }] });
      notify.success("File uploaded");
    } catch {
      notify.error("Upload failed", "Try again.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-3">
      {files.length > 0 && (
        <ul className="space-y-1">
          {files.map((file, index) => (
            <li key={index} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
              <span className="flex items-center gap-2 text-slate-700">
                <Icon name="fileText" size={16} className="text-slate-400" />
                {file.filename} · {(file.size / 1024).toFixed(1)} KB
              </span>
              {!disabled && (
                <Button variant="ghost" size="icon" aria-label="Remove file" onClick={() => onChange({ files: files.filter((_, i) => i !== index) })}>
                  <Icon name="trash" size={14} />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {!disabled && files.length < maxFiles && (
        <FileDropzone file={null} onFileChange={(file) => file && void upload(file)} accept={accept} maxBytes={maxSizeMb * 1024 * 1024} hint={`Up to ${maxSizeMb} MB`} />
      )}
      {(requesting || uploading) && <p className="text-xs text-slate-500">Uploading…</p>}
    </div>
  );
}
