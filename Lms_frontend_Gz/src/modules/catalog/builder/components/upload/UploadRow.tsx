import { cn } from "@/core/lib/cn";
import type { LessonUpload } from "@/modules/catalog/builder/hooks/useLessonUploads";
import { Button, Icon } from "@/shared/ui";

const STATE_TEXT: Record<LessonUpload["state"], string> = {
  uploading: "",
  processing: "Getting it ready to stream. You can close this window.",
  ready: "Ready",
  failed: "Failed",
  cancelled: "Cancelled",
};

/** One file on its way to becoming a lesson: progress, then processing/ready, or what went wrong. */
export function UploadRow({ upload, onCancel, onDismiss }: { upload: LessonUpload; onCancel: () => void; onDismiss: () => void }) {
  const isPdf = upload.kind === "pdf";
  const finished = upload.state !== "uploading";
  return (
    <li className="flex items-center gap-3 rounded-2xl bg-white p-3.5 ring-1 ring-slate-200">
      <span className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-[11px] font-extrabold", isPdf ? "bg-accent-50 text-accent-700" : "bg-navy-50 text-navy-700")}>
        {isPdf ? "PDF" : <Icon name="video" size={20} />}
      </span>
      <div className="min-w-0 flex-1 space-y-1.5">
        <p className="truncate text-sm font-semibold text-navy-950">{upload.title}</p>
        <p className="truncate text-xs text-slate-500">{upload.fileName} · {upload.sizeLabel}</p>
        {upload.state === "uploading" ? (
          <div className="flex items-center gap-3" role="progressbar" aria-valuenow={upload.percent} aria-valuemin={0} aria-valuemax={100} aria-label={`Uploading ${upload.title}`}>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200">
              <div className="h-full rounded-full bg-navy-600 transition-[width] duration-300" style={{ width: `${upload.percent}%` }} />
            </div>
            <span className="text-xs font-bold tabular-nums text-navy-700">{upload.percent}%</span>
          </div>
        ) : (
          <p className={cn("text-xs font-semibold", upload.state === "ready" ? "text-brand-700" : upload.state === "processing" ? "text-amber-700" : "text-red-600")}>
            {upload.state === "failed" && upload.error ? upload.error : STATE_TEXT[upload.state]}
          </p>
        )}
      </div>
      {finished ? (
        <Button variant="ghost" size="sm" onClick={onDismiss} aria-label={`Hide ${upload.title}`}>
          <Icon name="x" size={16} />
        </Button>
      ) : (
        <Button variant="secondary" size="sm" onClick={onCancel}>
          Cancel
        </Button>
      )}
    </li>
  );
}
