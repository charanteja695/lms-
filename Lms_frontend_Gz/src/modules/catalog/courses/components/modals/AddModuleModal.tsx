import { useState, useEffect } from "react";
import { X } from "lucide-react";

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
      await onSubmit({
        title: title.trim(),
        description: description.trim(),
        position: Number(position) || 1,
      });
      onClose();
    } catch (err: any) {
      setError(err?.message || "Failed to save module");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="w-full max-w-lg rounded-2xl bg-white shadow-2xl border border-slate-200 overflow-hidden animate-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-100 p-6 pb-4">
          <div>
            <h3 className="text-xl font-bold text-[#111827]">
              {initialData ? "Edit module" : "Add module"}
            </h3>
            <p className="text-sm text-slate-500 mt-0.5">Part of {courseTitle}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {error && (
            <div className="rounded-xl bg-rose-50 p-3 text-xs font-semibold text-rose-700 border border-rose-200">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-bold text-[#111827] mb-2">
              Module name *
            </label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="For example, Hooks and State Management"
              className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm text-[#111827] placeholder:text-slate-400 focus:border-[#096644] focus:ring-1 focus:ring-[#096644] focus:outline-none transition"
            />
          </div>

          <div>
            <label className="block text-sm font-bold text-[#111827] mb-2">
              Description
            </label>
            <textarea
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What students learn in this module"
              className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm text-[#111827] placeholder:text-slate-400 focus:border-[#096644] focus:ring-1 focus:ring-[#096644] focus:outline-none resize-none transition"
            />
          </div>

          <div className="max-w-[200px]">
            <label className="block text-sm font-bold text-[#111827] mb-2">
              Module order
            </label>
            <input
              type="number"
              min={1}
              value={position}
              onChange={(e) => setPosition(Number(e.target.value))}
              className="w-full rounded-xl border border-slate-300 px-4 py-2.5 text-sm text-[#111827] font-semibold focus:border-[#096644] focus:ring-1 focus:ring-[#096644] focus:outline-none transition"
            />
            <span className="text-xs text-slate-500 mt-1.5 block">
              Students finish modules in this order.
            </span>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              className="px-6 py-2.5 rounded-full border border-slate-300 bg-white text-sm font-semibold text-[#111827] hover:bg-slate-50 cursor-pointer transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="px-6 py-2.5 rounded-full bg-[#096644] hover:bg-[#075336] text-sm font-bold text-white shadow-xs cursor-pointer transition disabled:opacity-50"
            >
              {isSaving ? "Saving..." : initialData ? "Save changes" : "Add module"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
