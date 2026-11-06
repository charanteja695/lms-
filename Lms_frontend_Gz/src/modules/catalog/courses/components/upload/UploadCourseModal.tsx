import { useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { toApiError } from "@/core/lib/apiError";
import { cn } from "@/core/lib/cn";
import { uploadWithProgress } from "@/core/lib/uploadWithProgress";
import {
  useCreateCourseMutation,
  useCreateDraftVersionMutation,
} from "@/modules/catalog/courses/api/coursesApi";
import {
  useCreateModuleMutation,
  useCreateTopicMutation,
  useCreateItemMutation,
} from "@/modules/catalog/courses/api/curriculumApi";
import {
  useCompleteUploadMutation,
  useRequestUploadMutation,
} from "@/modules/media/api/mediaApi";
import {
  Button,
  Field,
  Icon,
  Input,
  Modal,
  Textarea,
} from "@/shared/ui";

const CATEGORIES = [
  "Computer Science & IT",
  "Data Science & AI",
  "Web Development",
  "Cloud & DevOps",
  "Cybersecurity",
  "Business & Management",
  "Design & UI/UX",
  "General Education",
];

interface PendingFile {
  id: string;
  file: File;
  kind: "video" | "pdf";
  percent: number;
  status: "pending" | "uploading" | "ready" | "failed";
  error?: string;
}

export function UploadCourseModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const notify = useNotify();

  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [summary, setSummary] = useState("");
  const [moduleTitle, setModuleTitle] = useState("Module 1: Introduction");
  const [topicTitle, setTopicTitle] = useState("Getting Started");
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [uploadStep, setUploadStep] = useState<string>("");

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dropKind, setDropKind] = useState<"video" | "pdf">("video");
  const [isDragging, setIsDragging] = useState(false);

  const [createCourse] = useCreateCourseMutation();
  const [createDraft] = useCreateDraftVersionMutation();
  const [createModule] = useCreateModuleMutation();
  const [createTopic] = useCreateTopicMutation();
  const [createItem] = useCreateItemMutation();
  const [requestUpload] = useRequestUploadMutation();
  const [completeUpload] = useCompleteUploadMutation();

  const handleTitleChange = (val: string) => {
    setTitle(val);
    if (!slug || slug === title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")) {
      setSlug(
        val
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "-")
          .replace(/^-|-$/g, "")
      );
    }
  };

  const handleAddFiles = (files: FileList | null, kind: "video" | "pdf") => {
    if (!files || files.length === 0) return;
    const newItems: PendingFile[] = Array.from(files).map((f) => ({
      id: crypto.randomUUID(),
      file: f,
      kind,
      percent: 0,
      status: "pending",
    }));
    setPendingFiles((prev) => [...prev, ...newItems]);
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files) {
      handleAddFiles(e.dataTransfer.files, dropKind);
    }
  };

  const removeFile = (id: string) => {
    setPendingFiles((prev) => prev.filter((item) => item.id !== id));
  };

  const handleSubmit = async () => {
    if (!title.trim()) {
      notify.error("Course title is required");
      return;
    }
    if (!slug.trim()) {
      notify.error("Course slug is required");
      return;
    }

    setIsSubmitting(true);
    setUploadStep("Creating course...");

    try {
      const formattedSummary = category ? `[${category}] ${summary.trim()}` : summary.trim();
      const course = await createCourse({
        title: title.trim(),
        slug: slug.trim(),
        summary: formattedSummary || "Course content and materials.",
      }).unwrap();

      let versionId = course.versions?.[0]?.version_id;
      if (!versionId) {
        setUploadStep("Setting up initial draft version...");
        const draft = await createDraft(course.course_id).unwrap();
        versionId = draft.version_id;
      }

      if (pendingFiles.length > 0 || moduleTitle) {
        setUploadStep("Creating course module and topic...");
        const newModuleRes = await createModule({
          courseId: course.course_id,
          versionId,
          body: { title: moduleTitle || "Module 1: Introduction" },
        }).unwrap();
        const moduleId = newModuleRes.module.module_id;

        const newTopicRes = await createTopic({
          courseId: course.course_id,
          versionId,
          moduleId,
          body: { title: topicTitle || "Getting Started" },
        }).unwrap();
        const topicId = newTopicRes.topic.topic_id;

        for (let i = 0; i < pendingFiles.length; i++) {
          const item = pendingFiles[i];
          if (!item) continue;
          setUploadStep(`Uploading ${item.file.name} (${i + 1}/${pendingFiles.length})...`);
          setPendingFiles((prev) =>
            prev.map((f) => (f.id === item.id ? { ...f, status: "uploading" } : f))
          );

          try {
            const { asset, upload } = await requestUpload({
              original_filename: item.file.name,
              content_type: item.file.type || (item.kind === "pdf" ? "application/pdf" : "video/mp4"),
              byte_size: item.file.size,
              context_type: "topic",
              context_id: topicId,
            }).unwrap();

            const lessonTitle = item.file.name
              .replace(/\.[^.]+$/, "")
              .replace(/[-_]+/g, " ")
              .trim();

            await createItem({
              courseId: course.course_id,
              versionId,
              moduleId,
              topicId,
              body: { item_type: item.kind, title: lessonTitle, media_id: asset.asset_id },
            }).unwrap();

            const sending = uploadWithProgress(
              upload,
              item.file,
              item.file.name,
              (percent) => {
                setPendingFiles((prev) =>
                  prev.map((f) => (f.id === item.id ? { ...f, percent } : f))
                );
              }
            );

            await sending.done;
            await completeUpload(asset.asset_id).unwrap();

            setPendingFiles((prev) =>
              prev.map((f) => (f.id === item.id ? { ...f, percent: 100, status: "ready" } : f))
            );
          } catch (fileErr) {
            setPendingFiles((prev) =>
              prev.map((f) =>
                f.id === item.id
                  ? { ...f, status: "failed", error: toApiError(fileErr).message }
                  : f
              )
            );
          }
        }
      }

      notify.success("Course uploaded successfully", `"${title}" has been created with materials.`);
      onClose();
      navigate(`/courses/${course.course_id}`);
    } catch (err) {
      notify.apiError(err, "Failed to upload course");
    } finally {
      setIsSubmitting(false);
      setUploadStep("");
    }
  };

  return (
    <Modal
      open={open}
      onClose={isSubmitting ? () => {} : onClose}
      size="lg"
      title="Upload Course"
      description="Create a new course with details, videos, and learning materials."
      footer={
        <div className="flex w-full items-center justify-between">
          <span className="text-xs text-slate-500">
            {uploadStep || (pendingFiles.length > 0 ? `${pendingFiles.length} file(s) queued` : "Ready to upload")}
          </span>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              loading={isSubmitting}
              icon="upload"
            >
              Upload Course
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-6 max-h-[70vh] overflow-y-auto px-1">
        {/* Basic Course Details */}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Course Title" required className="sm:col-span-2">
            {(props) => (
              <Input
                {...props}
                placeholder="e.g. Full-Stack Web Development Bootcamp"
                value={title}
                onChange={(e) => handleTitleChange(e.target.value)}
                disabled={isSubmitting}
              />
            )}
          </Field>

          <Field label="URL Slug" required>
            {(props) => (
              <Input
                {...props}
                placeholder="course-slug"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                disabled={isSubmitting}
              />
            )}
          </Field>

          <Field label="Category">
            {(props) => (
              <select
                {...props}
                className="select-chevron h-11 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-navy-950 focus:border-brand-500 focus:outline-none"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                disabled={isSubmitting}
              >
                {CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            )}
          </Field>

          <Field label="Course Summary & Description" className="sm:col-span-2">
            {(props) => (
              <Textarea
                {...props}
                rows={3}
                placeholder="Describe what learners will achieve, prerequisites, and learning objectives..."
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                disabled={isSubmitting}
              />
            )}
          </Field>
        </div>

        {/* Initial Structure & Content Upload */}
        <div className="rounded-2xl border border-slate-200/80 bg-slate-50/50 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-bold text-navy-950">Initial Course Content & Media</h3>
            <span className="text-xs text-slate-500">Optional · can also be added later in builder</span>
          </div>

          <div className="mb-4 grid gap-3 sm:grid-cols-2">
            <Field label="Initial Module Title">
              {(props) => (
                <Input
                  {...props}
                  placeholder="Module 1: Introduction"
                  value={moduleTitle}
                  onChange={(e) => setModuleTitle(e.target.value)}
                  disabled={isSubmitting}
                />
              )}
            </Field>
            <Field label="Initial Topic Title">
              {(props) => (
                <Input
                  {...props}
                  placeholder="Getting Started"
                  value={topicTitle}
                  onChange={(e) => setTopicTitle(e.target.value)}
                  disabled={isSubmitting}
                />
              )}
            </Field>
          </div>

          {/* Media Kind Selector */}
          <div className="mb-3 flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-700">Add content type:</span>
            <button
              type="button"
              onClick={() => setDropKind("video")}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium transition-colors",
                dropKind === "video"
                  ? "bg-brand-100 text-brand-800 ring-1 ring-brand-300"
                  : "bg-white text-slate-600 hover:bg-slate-100 ring-1 ring-slate-200"
              )}
            >
              <Icon name="video" size={14} /> Course Video (MP4, MOV, WebM)
            </button>
            <button
              type="button"
              onClick={() => setDropKind("pdf")}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium transition-colors",
                dropKind === "pdf"
                  ? "bg-accent-100 text-accent-800 ring-1 ring-accent-300"
                  : "bg-white text-slate-600 hover:bg-slate-100 ring-1 ring-slate-200"
              )}
            >
              <Icon name="fileText" size={14} /> Learning Material (PDF)
            </button>
          </div>

          {/* File Dropzone */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            className={cn(
              "flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center transition-colors",
              isDragging
                ? "border-brand-500 bg-brand-50"
                : "border-slate-300 bg-white hover:border-slate-400"
            )}
          >
            <span
              className={cn(
                "flex h-10 w-10 items-center justify-center rounded-xl",
                dropKind === "video" ? "bg-brand-50 text-brand-600" : "bg-accent-50 text-accent-600"
              )}
            >
              <Icon name={dropKind === "video" ? "video" : "fileText"} size={20} />
            </span>
            <p className="mt-2 text-sm font-semibold text-navy-950">
              Drag & drop course {dropKind === "video" ? "videos" : "materials"} here
            </p>
            <p className="text-xs text-slate-500">
              or{" "}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="font-bold text-brand-700 hover:text-brand-800"
              >
                browse from computer
              </button>
            </p>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept={dropKind === "video" ? "video/*" : "application/pdf"}
              className="hidden"
              onChange={(e) => handleAddFiles(e.target.files, dropKind)}
            />
          </div>

          {/* Pending / Uploading files list */}
          {pendingFiles.length > 0 && (
            <div className="mt-3 space-y-2">
              <p className="text-xs font-semibold text-slate-700">Files queued for upload:</p>
              {pendingFiles.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-2.5 text-xs shadow-sm"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      className={cn(
                        "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg",
                        item.kind === "video" ? "bg-brand-50 text-brand-700" : "bg-accent-50 text-accent-700"
                      )}
                    >
                      <Icon name={item.kind === "video" ? "video" : "fileText"} size={14} />
                    </span>
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-navy-950">{item.file.name}</p>
                      <p className="text-slate-400">
                        {(item.file.size / (1024 * 1024)).toFixed(1)} MB · {item.kind.toUpperCase()}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {item.status === "uploading" && (
                      <span className="font-semibold text-brand-700">{item.percent}%</span>
                    )}
                    {item.status === "ready" && (
                      <span className="flex items-center gap-1 font-semibold text-emerald-600">
                        <Icon name="check" size={14} /> Uploaded
                      </span>
                    )}
                    {item.status === "failed" && (
                      <span className="font-semibold text-rose-600" title={item.error}>
                        Failed
                      </span>
                    )}
                    {!isSubmitting && (
                      <button
                        type="button"
                        onClick={() => removeFile(item.id)}
                        className="text-slate-400 hover:text-rose-600"
                      >
                        <Icon name="x" size={14} />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}
