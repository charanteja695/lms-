import { SESSION_STATUS_LABELS, SESSION_STATUS_TONES } from "@/modules/proctoring/common/labels";
import type { SessionStatus } from "@/modules/proctoring/common/types";
import { Badge } from "@/shared/ui";

export function SessionStatusBadge({ status }: { status: SessionStatus }) {
  return <Badge tone={SESSION_STATUS_TONES[status]}>{SESSION_STATUS_LABELS[status]}</Badge>;
}
