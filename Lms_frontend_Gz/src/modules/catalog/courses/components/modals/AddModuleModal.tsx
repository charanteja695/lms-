import { useState, useEffect } from "react";
import { Icon } from "@/shared/ui";

interface AddModuleModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: { title: string; description: string; position: number }) => Promise<void>;
  initialData?: { title: string; description: string; position: number } | null;
  courseTitle?: string;
  defaultPosition?: number;
}

export function AddModuleModal({
  isOpen,
  onClose,
  onSubmit,
  initialData,
  courseTitle = "Course",
  defaultPosition = 1,
}: AddModuleModalProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [position, setPosition] = useState(defaultPosition);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialData) {
      setTitle(initialData.title || "");
      setDescription(initialData.description || "");
      setPosition(initialData.position || defaultPosition);
    } else {
      setTitle("");
      setDescription("");
      setPosition(defaultPosition);
    }
    setError(null);
  }, [initialData, defaultPosition, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("Module name is required");
      return;
    }
    try {
      setIsSaving(true);
      setError(null);
      await onSubmit({ title: title.trim(), description: description.trim(), position: Number(position) || 1 });
      onClose();
    } catch (err: any) {
      setError(err?.message || "Failed to save module");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-xs">
      <div className="w-full max-w-lg rounded-2xl bg-white shadow-xl border border-slate-200 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-start justify-between border-b border-slate-100 p-5 pb-4">
          <div>
            <h3 className="text-base font-bold text-[#0A1530]">
              {initialData ? "Edit module" : "Add module"}
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">Part of {courseTitle}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 cursor-pointer"
          >
            <Icon name="x" size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {error && (
            <div className="rounded-lg bg-rose-50 p-3 text-xs font-semibold text-rose-700 border border-rose-200">
              {error}
            </div>
          )}

          <div>
            <label className="block text-xs font-bold text-slate-800 mb-1.5">Module name *</label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="For example, Hooks and State Management"
              className="w-full rounded-xl border border-slate-300 px-3.5 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-[#00663C] focus:outline-none focus:ring-1 focus:ring-[#00663C]"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-800 mb-1.5">Description</label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What students learn in this module"
              className="w-full rounded-xl border border-slate-300 px-3.5 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-[#00663C] focus:outline-none focus:ring-1 focus:ring-[#00663C] resize-none"
            />
          </div>

          <div className="max-w-[180px]">
            <label className="block text-xs font-bold text-slate-800 mb-1.5">Module order</label>
            <input
              type="number"
              min={1}
              value={position}
              onChange={(e) => setPosition(Number(e.target.value))}
              className="w-full rounded-xl border border-slate-300 px-3.5 py-2 text-sm text-slate-900 focus:border-[#00663C] focus:outline-none focus:ring-1 focus:ring-[#00663C]"
            />
            <span className="text-[11px] text-slate-400 mt-1 block">Students finish modules in this order.</span>
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              className="px-4 py-2 rounded-xl border border-slate-300 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="px-4 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] disabled:opacity-50 cursor-pointer shadow-xs"
            >
              {isSaving ? "Saving..." : initialData ? "Save changes" : "Add module"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
