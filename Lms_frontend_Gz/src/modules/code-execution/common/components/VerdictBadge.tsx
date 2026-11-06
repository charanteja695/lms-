import { VERDICT_LABELS, VERDICT_TONES } from "@/modules/code-execution/common/labels";
import type { Verdict } from "@/modules/code-execution/common/types";
import { Badge } from "@/shared/ui";

export function VerdictBadge({ verdict }: { verdict: Verdict | null }) {
  if (!verdict) return <Badge tone="gray">Pending</Badge>;
  return <Badge tone={VERDICT_TONES[verdict]}>{VERDICT_LABELS[verdict]}</Badge>;
}
