import { CASE_STATUS_LABELS, CASE_STATUS_TONES } from "@/modules/proctoring/common/labels";
import type { CaseStatus } from "@/modules/proctoring/common/types";
import { Badge } from "@/shared/ui";

export function CaseStatusBadge({ status }: { status: CaseStatus }) {
  return <Badge tone={CASE_STATUS_TONES[status]}>{CASE_STATUS_LABELS[status]}</Badge>;
}
