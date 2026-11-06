import { PRIORITY_LABELS, PRIORITY_TONES, STATUS_LABELS, STATUS_TONES, STUDENT_STATUS_LABELS } from "@/modules/support/common/labels";
import type { Priority, TicketStatus } from "@/modules/support/common/types";
import { Badge } from "@/shared/ui";

export function TicketStatusBadge({ status, forStudent = false }: { status: TicketStatus; forStudent?: boolean }) {
  return <Badge tone={STATUS_TONES[status]}>{(forStudent ? STUDENT_STATUS_LABELS : STATUS_LABELS)[status]}</Badge>;
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  return <Badge tone={PRIORITY_TONES[priority]}>{PRIORITY_LABELS[priority]}</Badge>;
}
