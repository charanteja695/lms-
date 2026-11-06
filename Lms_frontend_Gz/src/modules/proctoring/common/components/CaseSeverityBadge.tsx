import { CASE_SEVERITY_LABELS, CASE_SEVERITY_TONES } from "@/modules/proctoring/common/labels";
import type { CaseSeverity } from "@/modules/proctoring/common/types";
import { Badge } from "@/shared/ui";

export function CaseSeverityBadge({ severity }: { severity: string }) {
  const known = severity as CaseSeverity;
  return <Badge tone={CASE_SEVERITY_TONES[known] ?? "gray"}>{CASE_SEVERITY_LABELS[known] ?? severity}</Badge>;
}
