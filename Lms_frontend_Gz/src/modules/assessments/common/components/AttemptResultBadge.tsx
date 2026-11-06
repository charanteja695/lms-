import { ATTEMPT_RESULT_LABELS, ATTEMPT_RESULT_TONES } from "@/modules/assessments/common/labels";
import type { AttemptResult } from "@/modules/assessments/common/types";
import { Badge } from "@/shared/ui";

export function AttemptResultBadge({ result }: { result: AttemptResult }) {
  return <Badge tone={ATTEMPT_RESULT_TONES[result]}>{ATTEMPT_RESULT_LABELS[result]}</Badge>;
}
