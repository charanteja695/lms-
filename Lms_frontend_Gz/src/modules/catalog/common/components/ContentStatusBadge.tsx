import { CONTENT_STATUS_LABELS, CONTENT_STATUS_TONES } from "@/modules/catalog/common/labels";
import type { ContentStatus } from "@/modules/catalog/common/types";
import { Badge } from "@/shared/ui";

export function ContentStatusBadge({ status }: { status: ContentStatus }) {
  return <Badge tone={CONTENT_STATUS_TONES[status]}>{CONTENT_STATUS_LABELS[status]}</Badge>;
}
