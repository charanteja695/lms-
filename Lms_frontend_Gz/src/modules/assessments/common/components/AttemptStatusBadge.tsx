import { ATTEMPT_STATUS_LABELS, ATTEMPT_STATUS_TONES } from "@/modules/assessments/common/labels";
import type { AttemptStatus } from "@/modules/assessments/common/types";
import { Badge } from "@/shared/ui";

export function AttemptStatusBadge({ status }: { status: AttemptStatus }) {
  return <Badge tone={ATTEMPT_STATUS_TONES[status]}>{ATTEMPT_STATUS_LABELS[status]}</Badge>;
}
