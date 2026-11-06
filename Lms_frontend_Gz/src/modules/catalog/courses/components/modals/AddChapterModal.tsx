import { useState, useEffect, useRef } from "react";
import { Icon, Spinner } from "@/shared/ui";
import { useAppSelector } from "@/app/hooks";
import { uploadMediaMultipart } from "@/modules/media/api/uploadMediaMultipart";

export interface ChapterMaterial {
  type: "video" | "pdf" | "note";
  name: string;
  size?: string;
  status: "uploaded" | "uploading";
  progress?: number;
  media_id?: string;
  url?: string;
}

interface AddChapterModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: {
    title: string;
    position: number;
    description: string;
    objectives: string[];
    materials: ChapterMaterial[];
  }) => Promise<void>;
  initialData?: {
    title: string;
    position: number;
    description: string;
    objectives?: string[];
  } | null;
  moduleTitle?: string;
  defaultPosition?: number;
  courseId?: string;
  moduleId?: string;
}

export function AddChapterModal({
  isOpen,
  onClose,
  onSubmit,
  initialData,
  moduleTitle = "Module",
  defaultPosition = 1,
  courseId,
  moduleId,
}: AddChapterModalProps) {
  const [title, setTitle] = useState("");
  const [position, setPosition] = useState(defaultPosition);
  const [description, setDescription] = useState("");
  const [objectives, setObjectives] = useState<string[]>([""]);
  const [materials, setMaterials] = useState<ChapterMaterial[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadType, setUploadType] = useState<"video" | "pdf" | "note">("video");
  const token = useAppSelector((state) => state.auth.accessToken);

  useEffect(() => {
    if (initialData) {
      setTitle(initialData.title || "");
      setPosition(initialData.position || defaultPosition);
      setDescription(initialData.description || "");
      setObjectives(initialData.objectives && initialData.objectives.length > 0 ? initialData.objectives : [""]);
    } else {
      setTitle("");
      setPosition(defaultPosition);
      setDescription("");
      setObjectives([""]);
      setMaterials([]);
    }
    setError(null);
  }, [initialData, defaultPosition, isOpen]);

  if (!isOpen) return null;

  const handleAddObjective = () => {
    setObjectives((prev) => [...prev, ""]);
  };

  const handleObjectiveChange = (index: number, val: string) => {
    setObjectives((prev) => {
      const next = [...prev];
      next[index] = val;
      return next;
    });
  };

  const handleRemoveObjective = (index: number) => {
    setObjectives((prev) => prev.filter((_, i) => i !== index));
  };

  const handleTriggerUpload = (type: "video" | "pdf" | "note") => {
    setUploadType(type);
    if (fileInputRef.current) {
      if (type === "video") fileInputRef.current.accept = "video/mp4,video/webm,video/mov,video/*";
      else if (type === "pdf") fileInputRef.current.accept = "application/pdf";
      else fileInputRef.current.accept = ".txt,.md,text/plain,text/markdown";
      fileInputRef.current.click();
    }
  };

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || !e.target.files[0]) return;
    const file = e.target.files[0];
    const sizeStr = (file.size / (1024 * 1024)).toFixed(1) + " MB";
    const matIndex = materials.length;

    // Add placeholder in uploading state
    setMaterials((prev) => [
      ...prev,
      {
        type: uploadType,
        name: file.name,
        size: sizeStr,
        status: "uploading",
        progress: 10,
      },
    ]);

    try {
      if (uploadType === "video" || uploadType === "pdf") {
        const res = await uploadMediaMultipart({
          file,
          kind: uploadType,
          token,
          courseId,
          moduleId,
          onProgress: (pct) => {
            setMaterials((prev) => {
              const updated = [...prev];
              if (updated[matIndex]) {
                updated[matIndex] = { ...updated[matIndex], progress: pct };
              }
              return updated;
            });
          },
        });

        setMaterials((prev) => {
          const updated = [...prev];
          if (updated[matIndex]) {
            updated[matIndex] = {
              ...updated[matIndex],
              status: "uploaded",
              progress: 100,
              media_id: res.asset_id,
              url: res.url,
            };
          }
          return updated;
        });
      } else {
        // Text / notes don't need binary media streaming
        setMaterials((prev) => {
          const updated = [...prev];
          if (updated[matIndex]) {
            updated[matIndex] = { ...updated[matIndex], status: "uploaded", progress: 100 };
          }
          return updated;
        });
      }
    } catch (err: any) {
      setError(err?.message || "Failed to upload file to media service");
      setMaterials((prev) => prev.filter((_, i) => i !== matIndex));
    }
  };

  const handleRemoveMaterial = (index: number) => {
    setMaterials((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("Chapter name is required");
      return;
    }
    const hasUploading = materials.some((m) => m.status === "uploading");
    if (hasUploading) {
      setError("Please wait for all media files to finish uploading");
      return;
    }

    try {
      setIsSaving(true);
      setError(null);
      await onSubmit({
        title: title.trim(),
        position: Number(position) || 1,
        description: description.trim(),
        objectives: objectives.filter((o) => o.trim().length > 0),
        materials,
      });
      onClose();
    } catch (err: any) {
      setError(err?.message || "Failed to save chapter");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-xs overflow-y-auto">
      <div className="w-full max-w-xl rounded-2xl bg-white shadow-xl border border-slate-200 overflow-hidden my-8">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-[#0A1530]">
              {initialData ? "Edit chapter" : "Add chapter"}
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">{moduleTitle}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100"
          >
            <Icon name="x" size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4 max-h-[75vh] overflow-y-auto">
          {error && (
            <div className="p-3 rounded-xl bg-rose-50 text-rose-700 text-xs font-semibold border border-rose-200">
              {error}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
            <div className="sm:col-span-9">
              <label className="block text-xs font-bold text-slate-800 mb-1">
                Chapter name *
              </label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. JSX and Component Lifecycle"
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs text-slate-900 focus:border-[#00663C] focus:outline-none"
              />
            </div>
            <div className="sm:col-span-3">
              <label className="block text-xs font-bold text-slate-800 mb-1">Order #</label>
              <input
                type="number"
                min={1}
                value={position}
                onChange={(e) => setPosition(Number(e.target.value))}
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs text-slate-900 focus:border-[#00663C] focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-800 mb-1">
              Description / Summary
            </label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What will students learn in this chapter?"
              className="w-full rounded-xl border border-slate-300 p-3 text-xs text-slate-900 focus:border-[#00663C] focus:outline-none"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-bold text-slate-800">Learning objectives</label>
              <button
                type="button"
                onClick={handleAddObjective}
                className="text-[11px] font-bold text-[#00663C] hover:underline"
              >
                + Add objective
              </button>
            </div>
            <div className="space-y-2">
              {objectives.map((obj, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={obj}
                    onChange={(e) => handleObjectiveChange(i, e.target.value)}
                    placeholder={`Objective ${i + 1}`}
                    className="flex-1 rounded-xl border border-slate-300 px-3 py-1.5 text-xs text-slate-900 focus:border-[#00663C] focus:outline-none"
                  />
                  {objectives.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveObjective(i)}
                      className="p-1 text-slate-400 hover:text-rose-600"
                    >
                      <Icon name="x" size={14} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-800 mb-2">
              Upload study materials (Video, PDF or Notes)
            </label>
            <div className="grid grid-cols-3 gap-2 mb-3">
              <button
                type="button"
                onClick={() => handleTriggerUpload("video")}
                className="flex flex-col items-center justify-center p-3 rounded-xl border border-dashed border-slate-300 hover:border-[#00663C] hover:bg-emerald-50/50 transition-colors"
              >
                <Icon name="play" size={18} className="text-[#00663C] mb-1" />
                <span className="text-[11px] font-bold text-slate-700">Add Video</span>
                <span className="text-[10px] text-slate-400">MP4, WebM</span>
              </button>

              <button
                type="button"
                onClick={() => handleTriggerUpload("pdf")}
                className="flex flex-col items-center justify-center p-3 rounded-xl border border-dashed border-slate-300 hover:border-[#00663C] hover:bg-emerald-50/50 transition-colors"
              >
                <Icon name="fileText" size={18} className="text-[#00663C] mb-1" />
                <span className="text-[11px] font-bold text-slate-700">Add PDF</span>
                <span className="text-[10px] text-slate-400">Slides, Notes</span>
              </button>

              <button
                type="button"
                onClick={() => handleTriggerUpload("note")}
                className="flex flex-col items-center justify-center p-3 rounded-xl border border-dashed border-slate-300 hover:border-[#00663C] hover:bg-emerald-50/50 transition-colors"
              >
                <Icon name="book" size={18} className="text-[#00663C] mb-1" />
                <span className="text-[11px] font-bold text-slate-700">Add Notes</span>
                <span className="text-[10px] text-slate-400">Text, Markdown</span>
              </button>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              onChange={handleFileSelected}
            />

            {materials.length > 0 && (
              <div className="space-y-2 border border-slate-200 rounded-xl p-3 bg-slate-50">
                <span className="text-[11px] font-bold text-slate-700 block mb-1">
                  Attached files ({materials.length})
                </span>
                {materials.map((mat, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2 rounded-lg bg-white border border-slate-200 text-xs"
                  >
                    <div className="flex items-center gap-2 truncate">
                      <Icon
                        name={mat.type === "video" ? "play" : mat.type === "pdf" ? "fileText" : "book"}
                        size={14}
                        className="text-[#00663C] shrink-0"
                      />
                      <span className="truncate font-medium text-slate-800">{mat.name}</span>
                      {mat.size && <span className="text-[10px] text-slate-400">({mat.size})</span>}
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {mat.status === "uploading" ? (
                        <div className="flex items-center gap-1.5 text-[11px] text-[#00663C] font-semibold">
                          <Spinner size={12} className="text-[#00663C]" />
                          <span>{mat.progress || 0}%</span>
                        </div>
                      ) : (
                        <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
                          Ready
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={() => handleRemoveMaterial(idx)}
                        className="text-slate-400 hover:text-rose-600"
                      >
                        <Icon name="x" size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              className="px-4 py-2 rounded-xl border border-slate-300 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="px-4 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] disabled:opacity-50"
            >
              {isSaving ? "Saving..." : initialData ? "Save changes" : "Create chapter"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
