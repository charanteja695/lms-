import { useState } from "react";

import { cn } from "@/core/lib/cn";
import type { TopicItem } from "@/modules/catalog/courses/curriculumTypes";
import { useGetMediaAssetQuery } from "@/modules/media/api/mediaApi";
import { LessonMedia } from "@/modules/media/components/LessonMedia";
import { Badge, Button, Icon, Menu, Modal } from "@/shared/ui";

const minutes = (seconds: number) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

/** A video or PDF still being processed: asks media-service until it is ready (or failed). */
function MediaState({ mediaId }: { mediaId: string }) {
  const { data } = useGetMediaAssetQuery(mediaId, { pollingInterval: 5000 });
  if (data?.status === "failed") return <Badge tone="red">Failed</Badge>;
  if (data?.status === "uploading") return <Badge tone="blue">Uploading</Badge>;
  return <Badge tone="amber">Processing</Badge>;
}

export function LessonRow({ item, index, count, editable, onRename, onDelete, onMove }: {
  item: TopicItem;
  index: number;
  count: number;
  editable: boolean;
  onRename: () => void;
  onDelete: () => void;
  onMove: (step: -1 | 1) => void;
}) {
  const [previewing, setPreviewing] = useState(false);
  const isPdf = item.item_type === "pdf";
  const hasMedia = (item.item_type === "video" || isPdf) && item.media_id;
  const meta = isPdf ? "PDF" : item.item_type === "video" ? (item.duration_seconds ? `Video · ${minutes(item.duration_seconds)}` : "Video") : item.item_type === "notes" ? "Notes" : "Practice";

  return (
    <li className="flex items-center gap-3 rounded-xl px-2.5 py-2 transition-colors hover:bg-slate-50">
      <span className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[11px] font-extrabold", isPdf ? "bg-accent-50 text-accent-700" : "bg-navy-50 text-navy-700")}>
        {isPdf ? "PDF" : <Icon name={item.item_type === "video" ? "video" : "fileText"} size={17} />}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-slate-900">{item.title}</p>
        <p className="text-xs text-slate-500">{meta}</p>
      </div>
      {hasMedia && (item.media_ready ? <Badge tone="green">Ready</Badge> : <MediaState mediaId={item.media_id as string} />)}
      <Menu
        trigger={
          <Button variant="ghost" size="icon" aria-label={`More for ${item.title}`}>
            <Icon name="more" size={18} />
          </Button>
        }
        items={[
          { label: "Preview", icon: "eye", hidden: !(hasMedia && item.media_ready), onSelect: () => setPreviewing(true) },
          { label: "Rename", icon: "edit", hidden: !editable, onSelect: onRename },
          { label: "Move up", icon: "arrowUp", hidden: !editable || index === 0, onSelect: () => onMove(-1) },
          { label: "Move down", icon: "arrowDown", hidden: !editable || index === count - 1, onSelect: () => onMove(1) },
          { label: "Delete", icon: "trash", tone: "danger", hidden: !editable, onSelect: onDelete },
        ]}
      />
      {previewing && hasMedia && (
        <Modal open onClose={() => setPreviewing(false)} size="lg" title={item.title}>
          <LessonMedia mediaId={item.media_id as string} kind={isPdf ? "pdf" : "video"} title={item.title} />
        </Modal>
      )}
    </li>
  );
}
