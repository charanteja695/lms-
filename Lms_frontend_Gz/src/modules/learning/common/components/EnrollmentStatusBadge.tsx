import { ENROLLMENT_STATUS_LABELS, ENROLLMENT_STATUS_TONES } from "@/modules/learning/common/labels";
import type { EnrollmentStatus } from "@/modules/learning/common/types";
import { Badge } from "@/shared/ui";

export function EnrollmentStatusBadge({ status }: { status: EnrollmentStatus }) {
  return <Badge tone={ENROLLMENT_STATUS_TONES[status]}>{ENROLLMENT_STATUS_LABELS[status]}</Badge>;
}
