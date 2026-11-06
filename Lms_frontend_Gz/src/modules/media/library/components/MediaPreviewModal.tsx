import { formatBytes, formatDateTime } from "@/core/lib/format";
import { LessonMedia } from "@/modules/media/components/LessonMedia";
import type { MediaAsset } from "@/modules/media/types";
import { Modal } from "@/shared/ui";

/** Watch a video or read a PDF exactly as a learner would. */
export function MediaPreviewModal({ asset, onClose }: { asset: MediaAsset | null; onClose: () => void }) {
  if (!asset) return null;
  return (
    <Modal open onClose={onClose} size="lg" title={asset.original_filename} description={`${formatBytes(asset.byte_size)} · uploaded ${formatDateTime(asset.created_at)}`}>
      <LessonMedia mediaId={asset.asset_id} kind={asset.kind === "document" ? "pdf" : "video"} title={asset.original_filename} />
    </Modal>
  );
}
