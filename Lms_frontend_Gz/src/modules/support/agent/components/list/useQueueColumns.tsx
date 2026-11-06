import { useMemo } from "react";

import { formatDateTime, formatRelative } from "@/core/lib/format";
import { CATEGORY_LABELS, QUEUE_LABELS } from "@/modules/support/common/labels";
import { PriorityBadge, TicketStatusBadge } from "@/modules/support/common/components/TicketBadges";
import type { Ticket } from "@/modules/support/common/types";
import { UserNameCell } from "@/modules/user-management/common/components/UserNameCell";
import { Badge, type Column } from "@/shared/ui";

/** The next SLA deadline that matters: the first response until there is one, then resolution. */
function nextDue(ticket: Ticket): string | null {
  return ticket.first_response_at ? ticket.resolution_due_at : ticket.first_response_due_at;
}

export function useQueueColumns() {
  return useMemo<Column<Ticket>[]>(
    () => [
      {
        key: "subject",
        header: "Subject",
        render: (item) => (
          <div className="min-w-0">
            <p className="truncate font-medium text-slate-900">{item.subject}</p>
            <p className="text-xs text-slate-500">
              {CATEGORY_LABELS[item.category]} · {QUEUE_LABELS[item.queue]}
              {item.source === "ai-tutor" && " · from the AI tutor"}
            </p>
          </div>
        ),
      },
      { key: "requester", header: "Student", hideOnMobile: true, render: (item) => <UserNameCell userId={item.requester_user_id} /> },
      { key: "priority", header: "Priority", render: (item) => <PriorityBadge priority={item.priority} /> },
      { key: "status", header: "Status", render: (item) => <TicketStatusBadge status={item.status} /> },
      {
        key: "due",
        header: "Due",
        hideOnMobile: true,
        render: (item) =>
          item.first_response_breached || item.resolution_breached ? (
            <Badge tone="red">SLA breached</Badge>
          ) : nextDue(item) ? (
            <span title={formatDateTime(nextDue(item))}>{formatRelative(nextDue(item))}</span>
          ) : (
            "—"
          ),
      },
      { key: "assignee", header: "Assignee", hideOnMobile: true, render: (item) => (item.assignee_user_id ? <UserNameCell userId={item.assignee_user_id} /> : <span className="text-slate-400">Unassigned</span>) },
    ],
    [],
  );
}
