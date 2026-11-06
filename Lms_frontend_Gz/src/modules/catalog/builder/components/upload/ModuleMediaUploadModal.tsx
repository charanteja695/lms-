import { useRef, useState, type DragEvent } from "react";

import { useAppSelector } from "@/app/hooks";
import { useNotify } from "@/core/hooks/useNotify";
import { cn } from "@/core/lib/cn";
import {
  useCreateItemMutation,
  useCreateTopicMutation,
  useDeleteItemMutation,
} from "@/modules/catalog/courses/api/curriculumApi";
import type { ModuleDetail } from "@/modules/catalog/courses/curriculumTypes";
import { uploadMediaMultipart } from "@/modules/media/api/uploadMediaMultipart";
import { Button, Field, Icon, Input, Modal, Spinner, Tabs, Textarea } from "@/shared/ui";

export type UploadKind = "video" | "pdf";

interface ModuleMediaUploadModalProps {
  courseId: string;
  versionId: string;
  module: ModuleDetail;
  moduleNumber?: number;
  initialKind?: UploadKind;
  onClose: () => void;
  onSuccess?: () => void;
}

const ACCEPT: Record<UploadKind, string> = {
  video: "video/mp4,video/webm,video/quicktime,video/x-matroska",
  pdf: "application/pdf",
};

const HINT: Record<UploadKind, string> = {
  video: "MP4, WebM or MOV · up to 5 GB",
  pdf: "PDF document · up to 50 MB",
};

const formatSize = (bytes: number) => {
  if (bytes >= 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
};

const titleFromFilename = (name: string) =>
  name
    .replace(/\.[^.]+$/, "")
    .replace(/[-_]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 200) || "Lesson";

export function ModuleMediaUploadModal({
  courseId,
  versionId,
  module,
  moduleNumber,
  initialKind = "video",
  onClose,
  onSuccess,
}: ModuleMediaUploadModalProps) {
  const notify = useNotify();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<(() => void) | null>(null);

  const [kind, setKind] = useState<UploadKind>(initialKind);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);

  // Target topic selection:
  const hasTopics = module.topics.length > 0;
  const [targetTopicId, setTargetTopicId] = useState<string>(
    hasTopics ? module.topics[0]?.topic_id ?? "__new__" : "__new__"
  );
  const [newTopicTitle, setNewTopicTitle] = useState(
    hasTopics ? "" : `${module.title} Lessons`
  );

  // Upload lifecycle state
  const [percent, setPercent] = useState(0);
  const [status, setStatus] = useState<"idle" | "uploading" | "processing" | "ready" | "failed">(
    "idle"
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const token = useAppSelector((state) => state.auth.accessToken);
  const [createTopic] = useCreateTopicMutation();
  const [createItem] = useCreateItemMutation();
  const [deleteItem] = useDeleteItemMutation();

  const handleFile = (file: File | null) => {
    if (!file) {
      setSelectedFile(null);
      return;
    }
    // Validation
    if (kind === "pdf") {
      const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
      if (!isPdf) {
        setErrorMessage("Please select a valid PDF file.");
        return;
      }
      if (file.size > 50 * 1024 * 1024) {
        setErrorMessage("PDF file must be 50 MB or smaller.");
        return;
      }
    } else {
      const isVideo = file.type.startsWith("video/") || /\.(mp4|webm|mov|mkv)$/i.test(file.name);
      if (!isVideo) {
        setErrorMessage("Please select a valid video file (MP4, WebM, MOV).");
        return;
      }
      if (file.size > 5 * 1024 * 1024 * 1024) {
        setErrorMessage("Video file must be 5 GB or smaller.");
        return;
      }
    }

    setErrorMessage(null);
    setSelectedFile(file);
    if (!title.trim()) {
      setTitle(titleFromFilename(file.name));
    }
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    if (event.dataTransfer.files?.[0]) {
      handleFile(event.dataTransfer.files[0]);
    }
  };

  const handleCancel = () => {
    if (abortRef.current) {
      abortRef.current();
    }
    onClose();
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setErrorMessage(`Please select a ${kind === "video" ? "video" : "PDF"} file.`);
      return;
    }
    const lessonTitle = title.trim() || titleFromFilename(selectedFile.name);
    if (!lessonTitle) {
      setErrorMessage("Please enter a title for this lesson.");
      return;
    }

    setStatus("uploading");
    setPercent(0);
    setErrorMessage(null);

    let activeTopicId = targetTopicId;
    let createdItemId: string | null = null;

    try {
      // 1. Ensure target topic exists in this module
      if (activeTopicId === "__new__" || !activeTopicId) {
        const topicName =
          newTopicTitle.trim() ||
          `${lessonTitle} ${kind === "video" ? "Video" : "Material"}`;
        const newTopicRes = await createTopic({
          courseId,
          versionId,
          moduleId: module.module_id,
          body: { title: topicName },
        }).unwrap();
        activeTopicId = newTopicRes.topic.topic_id;
      }

      // 2. Direct multipart upload with real-time progress tracking
      const uploadResult = await uploadMediaMultipart(
        {
          file: selectedFile,
          kind,
          title: lessonTitle,
          description: description.trim() || undefined,
          courseId,
          moduleId: module.module_id,
          topicId: activeTopicId,
          token,
          onProgress: (pct) => setPercent(pct),
        },
        (abortFn) => {
          abortRef.current = abortFn;
        }
      );

      // 3. Create topic item in curriculum
      setStatus("processing");
      const item = await createItem({
        courseId,
        versionId,
        moduleId: module.module_id,
        topicId: activeTopicId,
        body: {
          item_type: kind,
          title: lessonTitle,
          content_text: description.trim() || undefined,
          media_id: uploadResult.asset_id,
          required: true,
        },
      }).unwrap();
      createdItemId = item.topic_item_id;

      setStatus("ready");
      setPercent(100);
      notify.success(
        `${kind === "video" ? "Video" : "Learning material"} uploaded to ${module.title}!`
      );
      onSuccess?.();
      setTimeout(() => {
        onClose();
      }, 800);
    } catch (err: unknown) {
      const isAbort =
        (err instanceof DOMException && err.name === "AbortError") ||
        (err instanceof Error && err.message.toLowerCase().includes("cancelled"));
      if (!isAbort) {
        // Rollback created item if upload failed
        if (createdItemId && activeTopicId && activeTopicId !== "__new__") {
          await deleteItem({
            courseId,
            versionId,
            moduleId: module.module_id,
            topicId: activeTopicId,
            topicItemId: createdItemId,
          })
            .unwrap()
            .catch(() => undefined);
        }
        setStatus("failed");
        console.error("Module media upload error:", err);
        let msg = "Upload failed. Please try again.";
        if (err instanceof Error) {
          msg = err.message;
        } else if (typeof err === "object" && err !== null) {
          const r = err as Record<string, any>;
          msg = r.data?.message || r.data?.detail || r.message || JSON.stringify(err);
        }
        setErrorMessage(msg);
      } else {
        setStatus("idle");
      }
    } finally {
      abortRef.current = null;
    }
  };

  const isBusy = status === "uploading" || status === "processing";

  return (
    <Modal
      open
      onClose={isBusy ? () => {} : onClose}
      size="lg"
      title={
        kind === "video"
          ? `Upload Video to ${module.title}`
          : `Upload PDF / Material to ${module.title}`
      }
      description={
        moduleNumber
          ? `Module ${moduleNumber}: ${module.title}`
          : `Module: ${module.title}`
      }
      footer={
        <div className="flex w-full items-center justify-between">
          <div className="text-xs text-slate-500">
            {isBusy ? (
              <span className="flex items-center gap-1.5 text-navy-800 font-semibold">
                <Spinner size={16} />
                {status === "uploading" ? `Uploading ${percent}%...` : "Processing media..."}
              </span>
            ) : status === "ready" ? (
              <span className="flex items-center gap-1 text-emerald-600 font-semibold">
                <Icon name="check" size={14} /> Completed
              </span>
            ) : (
              <span>Associates directly with this module.</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" onClick={handleCancel} disabled={status === "processing"}>
              {status === "ready" ? "Close" : "Cancel"}
            </Button>
            <Button
              variant="primary"
              icon={kind === "video" ? "video" : "upload"}
              onClick={handleUpload}
              disabled={!selectedFile || isBusy || status === "ready"}
            >
              {isBusy
                ? status === "uploading"
                  ? `Uploading (${percent}%)`
                  : "Finalizing..."
                : kind === "video"
                ? "Upload Video"
                : "Upload Material"}
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        {/* Type toggle */}
        <Tabs<UploadKind>
          variant="pills"
          value={kind}
          onChange={(newKind) => {
            if (!isBusy) {
              setKind(newKind);
              setSelectedFile(null);
              setErrorMessage(null);
            }
          }}
          tabs={[
            { value: "video", label: "Video Lesson" },
            { value: "pdf", label: "PDF / Learning Material" },
          ]}
        />

        {/* Video / Material title */}
        <Field
          label={kind === "video" ? "Video Title" : "Material Title"}
          hint="Clear name displayed in the course curriculum"
          required
        >
          {(props) => (
            <Input
              {...props}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={
                kind === "video"
                  ? "e.g. 01 - Getting Started with Syntax"
                  : "e.g. Cheatsheet & Summary Notes"
              }
              disabled={isBusy}
            />
          )}
        </Field>

        {/* Video / Material description */}
        <Field
          label="Description / Summary (Optional)"
          hint="Optional notes or key concepts covered in this lesson"
        >
          {(props) => (
            <Textarea
              {...props}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={
                kind === "video"
                  ? "Briefly describe what students will learn from this video..."
                  : "Briefly describe what is covered in this study material..."
              }
              rows={2}
              disabled={isBusy}
            />
          )}
        </Field>

        {/* Target Topic Selection */}
        {hasTopics ? (
          <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3.5 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-navy-950 uppercase tracking-wider">
                Topic within this Module
              </label>
              <span className="text-xs text-slate-500">
                {module.topics.length} existing topic(s)
              </span>
            </div>

            <select
              value={targetTopicId}
              onChange={(e) => setTargetTopicId(e.target.value)}
              disabled={isBusy}
              className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-navy-950 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            >
              {module.topics.map((t, idx) => (
                <option key={t.topic_id} value={t.topic_id}>
                  Topic {idx + 1}: {t.title} ({t.items.length} lessons)
                </option>
              ))}
              <option value="__new__">+ Create new topic in this module...</option>
            </select>

            {targetTopicId === "__new__" && (
              <div className="pt-1">
                <Field label="New Topic Title" required>
                  {(props) => (
                    <Input
                      {...props}
                      value={newTopicTitle}
                      onChange={(e) => setNewTopicTitle(e.target.value)}
                      placeholder="e.g. Core Concepts"
                      disabled={isBusy}
                    />
                  )}
                </Field>
              </div>
            )}
          </div>
        ) : (
          <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-3.5 space-y-2">
            <p className="text-xs font-semibold text-amber-900">
              This module doesn&apos;t have any topics yet. A topic will be created automatically for
              this {kind === "video" ? "video" : "material"}.
            </p>
            <Field label="Initial Topic Title" required>
              {(props) => (
                <Input
                  {...props}
                  value={newTopicTitle}
                  onChange={(e) => setNewTopicTitle(e.target.value)}
                  placeholder="e.g. Introduction & Lessons"
                  disabled={isBusy}
                />
              )}
            </Field>
          </div>
        )}

        {/* File selection dropzone */}
        <div>
          <label className="block text-xs font-bold text-navy-950 uppercase tracking-wider mb-1.5">
            Select {kind === "video" ? "Video File" : "PDF File"} *
          </label>

          {selectedFile ? (
            <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50/80 p-3.5">
              <div className="flex items-center gap-3 min-w-0">
                <span
                  className={cn(
                    "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl",
                    kind === "video"
                      ? "bg-brand-50 text-brand-700"
                      : "bg-accent-50 text-accent-700"
                  )}
                >
                  <Icon name={kind === "video" ? "video" : "fileText"} size={20} />
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold text-navy-950">{selectedFile.name}</p>
                  <p className="text-xs text-slate-500">
                    {formatSize(selectedFile.size)} · {selectedFile.type || "file"}
                  </p>
                </div>
              </div>

              {!isBusy && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSelectedFile(null);
                    if (fileInputRef.current) fileInputRef.current.value = "";
                  }}
                >
                  Change
                </Button>
              )}
            </div>
          ) : (
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              className={cn(
                "flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-6 text-center transition-colors cursor-pointer",
                dragging
                  ? "border-brand-500 bg-brand-50/60"
                  : "border-slate-300 bg-slate-50/50 hover:bg-slate-50 hover:border-slate-400"
              )}
              onClick={() => fileInputRef.current?.click()}
            >
              <span
                className={cn(
                  "flex h-12 w-12 items-center justify-center rounded-2xl mb-2",
                  kind === "video" ? "bg-navy-50 text-navy-700" : "bg-accent-50 text-accent-700"
                )}
              >
                <Icon name={kind === "video" ? "video" : "upload"} size={22} />
              </span>
              <p className="text-sm font-bold text-navy-950">
                Drag and drop your {kind === "video" ? "video" : "PDF"} here
              </p>
              <p className="text-xs text-slate-500 mt-1">
                or <span className="font-semibold text-brand-700">browse file</span> · {HINT[kind]}
              </p>
            </div>
          )}

          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPT[kind]}
            className="sr-only"
            onChange={(e) => {
              if (e.target.files?.[0]) handleFile(e.target.files[0]);
            }}
          />
        </div>

        {/* Upload Progress Indicator */}
        {isBusy && (
          <div className="space-y-1.5 rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-navy-950">
                {status === "uploading"
                  ? `Uploading ${kind === "video" ? "video" : "PDF"}...`
                  : "Processing media..."}
              </span>
              <span className="font-bold tabular-nums text-brand-700">{percent}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-brand-600 transition-all duration-300"
                style={{ width: `${percent}%` }}
              />
            </div>
            <p className="text-[11px] text-slate-500">
              {status === "uploading"
                ? "Streaming directly to storage. Please don't close this window."
                : "Saving metadata and preparing stream."}
            </p>
          </div>
        )}

        {/* Error message */}
        {errorMessage && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700 flex items-start gap-2">
            <Icon name="alert" size={16} className="shrink-0 mt-0.5 text-red-600" />
            <div>
              <p className="font-semibold">Upload notice</p>
              <p>{errorMessage}</p>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
