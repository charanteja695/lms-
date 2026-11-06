import { useRef, useState, type DragEvent } from "react";

import { cn } from "@/core/lib/cn";
import { Button } from "./Button";
import { Icon } from "./Icon";

export function FileDropzone({
  file,
  onFileChange,
  accept = ".csv,text/csv",
  maxBytes,
  hint,
}: {
  file: File | null;
  onFileChange: (file: File | null) => void;
  accept?: string;
  maxBytes?: number;
  hint?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const choose = (candidate: File | undefined) => {
    if (!candidate) return;

    // Validate empty file
    if (candidate.size === 0) {
      setError("The selected file is empty. Please choose a valid resume file.");
      return;
    }

    // Validate file extension against accept list
    if (accept) {
      const allowed = accept
        .split(",")
        .map((a) => a.trim().toLowerCase())
        .filter(Boolean);
      const name = candidate.name.toLowerCase();
      const extValid = allowed.some((ext) => {
        if (ext.startsWith(".")) return name.endsWith(ext);
        return candidate.type.toLowerCase().includes(ext.replace("*", ""));
      });
      if (allowed.length > 0 && !extValid) {
        const readable = allowed
          .filter((a) => a.startsWith("."))
          .map((a) => a.toUpperCase())
          .join(", ");
        setError(`Unsupported file format. Please upload a ${readable || "supported"} document.`);
        return;
      }
    }

    // Validate file size limit
    if (maxBytes && candidate.size > maxBytes) {
      setError(`The file is larger than ${Math.round(maxBytes / 1024 / 1024)} MB.`);
      return;
    }

    setError(null);
    onFileChange(candidate);
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    choose(event.dataTransfer.files?.[0]);
  };

  return (
    <div>
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-6 text-center transition-all",
          dragging
            ? "border-brand-500 bg-brand-50/70"
            : file
            ? "border-emerald-300 bg-emerald-50/30"
            : "border-slate-300 bg-slate-50/60 hover:bg-slate-50",
        )}
      >
        {file ? (
          <div className="flex flex-col items-center space-y-2">
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
              <Icon name="fileText" size={20} />
            </span>
            <div className="text-center">
              <p className="text-sm font-bold text-slate-900 truncate max-w-sm">{file.name}</p>
              <p className="text-xs text-slate-500 mt-0.5">
                {(file.size / 1024).toFixed(1)} KB · <span className="text-emerald-700 font-medium">Ready to process</span>
              </p>
            </div>
            <div className="flex items-center gap-2 pt-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setError(null);
                  onFileChange(null);
                }}
                className="text-xs text-red-600 hover:text-red-700 hover:bg-red-50 h-7 px-2.5"
              >
                Choose another file
              </Button>
            </div>
          </div>
        ) : (
          <>
            <Icon name="upload" size={24} className="mb-1.5 text-slate-400" />
            <p className="text-sm text-slate-700">
              Drag your resume here or{" "}
              <button
                type="button"
                className="font-semibold text-brand-600 hover:underline focus:outline-none"
                onClick={() => inputRef.current?.click()}
              >
                browse
              </button>
            </p>
            {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(event) => {
            choose(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
      </div>
      {error && (
        <div className="mt-2 flex items-center gap-1.5 text-xs text-red-600 font-medium">
          <Icon name="alert" size={14} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
