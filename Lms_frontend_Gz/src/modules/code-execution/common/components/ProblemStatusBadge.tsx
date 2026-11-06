import { PROBLEM_STATUS_LABELS, PROBLEM_STATUS_TONES } from "@/modules/code-execution/common/labels";
import type { ProblemStatus } from "@/modules/code-execution/common/types";
import { Badge } from "@/shared/ui";

export function ProblemStatusBadge({ status }: { status: ProblemStatus }) {
  return <Badge tone={PROBLEM_STATUS_TONES[status]}>{PROBLEM_STATUS_LABELS[status]}</Badge>;
}
