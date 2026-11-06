import { BATCH_STATUS_LABELS, BATCH_STATUS_TONES } from "@/modules/learning/common/labels";
import type { BatchStatus } from "@/modules/learning/common/types";
import { Badge } from "@/shared/ui";

export function BatchStatusBadge({ status }: { status: BatchStatus }) {
  return <Badge tone={BATCH_STATUS_TONES[status]}>{BATCH_STATUS_LABELS[status]}</Badge>;
}
