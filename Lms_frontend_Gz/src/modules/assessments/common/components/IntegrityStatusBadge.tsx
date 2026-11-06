import { INTEGRITY_STATUS_LABELS, INTEGRITY_STATUS_TONES } from "@/modules/assessments/common/labels";
import type { IntegrityStatus } from "@/modules/assessments/common/types";
import { Badge } from "@/shared/ui";

export function IntegrityStatusBadge({ status }: { status: IntegrityStatus }) {
  return <Badge tone={INTEGRITY_STATUS_TONES[status]}>{INTEGRITY_STATUS_LABELS[status]}</Badge>;
}
