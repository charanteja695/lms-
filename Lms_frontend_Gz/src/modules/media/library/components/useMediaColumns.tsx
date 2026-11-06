import { formatBytes, formatDate } from "@/core/lib/format";
import { KIND_LABELS, STATUS_LABELS, STATUS_TONES } from "@/modules/media/labels";
import type { MediaAsset } from "@/modules/media/types";
import { Badge, Button, Icon, type Column } from "@/shared/ui";

const duration = (seconds: number | null) => (seconds ? `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}` : "—");

export function useMediaColumns({ onPreview, onArchive, onRestore }: {
  onPreview: (asset: MediaAsset) => void;
  onArchive: (asset: MediaAsset) => void;
  onRestore: (asset: MediaAsset) => void;
}): Column<MediaAsset>[] {
  return [
    {
      key: "file",
      header: "File",
      render: (a) => (
        <span className="flex min-w-0 items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700 ring-1 ring-brand-100">
            <Icon name={a.kind === "video" ? "video" : "fileText"} size={17} />
          </span>
          <span className="min-w-0">
            <span className="block max-w-[320px] truncate font-semibold text-navy-950" title={a.original_filename}>{a.original_filename}</span>
            <span className="block text-xs text-slate-500">{KIND_LABELS[a.kind]}{a.failed_reason ? ` · ${a.failed_reason}` : ""}</span>
          </span>
        </span>
      ),
    },
    { key: "size", header: "Size", render: (a) => formatBytes(a.byte_size), hideOnMobile: true },
    { key: "length", header: "Length", render: (a) => (a.kind === "video" ? duration(a.duration_seconds) : "—"), hideOnMobile: true },
    { key: "status", header: "Status", render: (a) => <Badge tone={a.archived_at ? "gray" : STATUS_TONES[a.status]}>{a.archived_at ? "Archived" : STATUS_LABELS[a.status]}</Badge> },
    { key: "uploaded", header: "Uploaded", render: (a) => formatDate(a.created_at), hideOnMobile: true },
    {
      key: "actions",
      header: "",
      render: (a) => (
        <span className="inline-flex items-center gap-1">
          {a.status === "ready" && !a.archived_at && <Button size="sm" variant="ghost" icon="eye" onClick={() => onPreview(a)}>Preview</Button>}
          {a.archived_at ? (
            <Button size="sm" variant="ghost" icon="refresh" onClick={() => onRestore(a)}>Restore</Button>
          ) : (
            <Button size="sm" variant="ghost" icon="archive" onClick={() => onArchive(a)}>Archive</Button>
          )}
        </span>
      ),
    },
  ];
}
