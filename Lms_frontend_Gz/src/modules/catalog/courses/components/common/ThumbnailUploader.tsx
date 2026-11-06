import { useState, useRef, type DragEvent, type ChangeEvent } from "react";
import { cn } from "@/core/lib/cn";
import { Spinner } from "@/shared/ui";
import { useAppSelector } from "@/app/hooks";
import { uploadMediaMultipart } from "@/modules/media/api/uploadMediaMultipart";

interface ThumbnailUploaderProps {
  value?: string | null;
  mediaId?: string | null;
  onChange: (url: string | null, mediaId: string | null) => void;
  className?: string;
  error?: string;
}

export function ThumbnailUploader({ value, onChange, className, error }: ThumbnailUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const token = useAppSelector((state) => state.auth.accessToken);

  const handleFile = async (file: File) => {
    setLocalError(null);
    if (!["image/png", "image/jpeg", "image/jpg", "image/webp"].includes(file.type)) {
      setLocalError("Only PNG or JPG files are allowed.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setLocalError("Image must be smaller than 5 MB.");
      return;
    }

    try {
      setIsUploading(true);
      setUploadProgress(0);
      const res = await uploadMediaMultipart({
        file,
        kind: "image",
        token,
        onProgress: (pct) => setUploadProgress(pct),
      });
      onChange(res.url, res.asset_id);
    } catch (err: any) {
      setLocalError(err.message || "Failed to upload thumbnail.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      void handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      void handleFile(e.target.files[0]);
    }
  };

  return (
    <div className={cn("space-y-2", className)}>
      <label className="block text-xs font-bold text-slate-800 tracking-wide">
        Course thumbnail
      </label>

      {isUploading ? (
        <div className="relative border-2 border-dashed border-emerald-400 bg-emerald-50/40 rounded-2xl p-6 text-center flex flex-col items-center justify-center min-h-[190px]">
          <Spinner size={32} className="text-[#00663C] mb-2" />
          <b className="text-sm font-bold text-[#0A1530] mb-1">Uploading thumbnail...</b>
          <span className="text-xs text-slate-500 font-medium">{uploadProgress}% complete</span>
        </div>
      ) : value ? (
        <div className="relative rounded-2xl overflow-hidden border border-slate-200 bg-slate-50 group aspect-video max-w-sm">
          <img
            src={value}
            alt="Course thumbnail preview"
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-slate-950/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="px-3 py-1.5 rounded-lg bg-white text-xs font-semibold text-slate-800 shadow-sm hover:bg-slate-100 cursor-pointer"
            >
              Change
            </button>
            <button
              type="button"
              onClick={() => onChange(null, null)}
              className="px-3 py-1.5 rounded-lg bg-rose-600 text-xs font-semibold text-white shadow-sm hover:bg-rose-700 cursor-pointer"
            >
              Remove
            </button>
          </div>
        </div>
      ) : (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={cn(
            "relative border-2 border-dashed rounded-2xl p-6 text-center cursor-pointer transition-colors bg-[#F8FAF9] flex flex-col items-center justify-center min-h-[190px]",
            isDragging
              ? "border-emerald-600 bg-emerald-50/50"
              : "border-slate-300 hover:border-emerald-500 hover:bg-[#F2F7F4]"
          )}
        >
          {/* Upload circle icon matching Screenshot 2 */}
          <div className="w-12 h-12 rounded-full bg-[#E7F3EC] text-[#00663C] flex items-center justify-center mb-2.5 transition-transform group-hover:scale-105">
            <svg
              className="w-5 h-5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 16V4M7 9l5-5 5 5M4 20h16" />
            </svg>
          </div>

          <b className="text-[14px] font-bold text-[#0A1530] mb-0.5">
            Upload thumbnail
          </b>
          <p className="text-[12px] text-slate-500 mb-0.5">
            Drag and drop, or browse
          </p>
          <span className="text-[11px] text-slate-400 font-medium">
            PNG or JPG, up to 5 MB
          </span>
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/jpg,image/webp"
        onChange={handleInputChange}
        className="hidden"
      />

      {(localError || error) && (
        <p className="text-xs text-rose-600 font-medium">{localError || error}</p>
      )}
    </div>
  );
}
