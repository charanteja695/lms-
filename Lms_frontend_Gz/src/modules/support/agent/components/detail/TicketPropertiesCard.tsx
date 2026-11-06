import { useNotify } from "@/core/hooks/useNotify";
import { formatDateTime } from "@/core/lib/format";
import { toOptions } from "@/core/lib/options";
import { CATEGORY_LABELS, PRIORITY_LABELS, QUEUE_LABELS } from "@/modules/support/common/labels";
import type { Category, Priority, TicketDetail } from "@/modules/support/common/types";
import { useUpdateTicketMutation } from "@/modules/support/agent/api/agentTicketsApi";
import { Badge, Card, DescriptionList, Select } from "@/shared/ui";

function due(at: string | null, breached: boolean, done: string | null) {
  if (done) return <span className="text-slate-500">Met {formatDateTime(done)}</span>;
  if (breached) return <Badge tone="red">Breached</Badge>;
  return at ? formatDateTime(at) : "—";
}

/** Priority and category are editable (a new category may move it to another queue; priority recomputes the SLA). */
export function TicketPropertiesCard({ detail }: { detail: TicketDetail }) {
  const notify = useNotify();
  const [update, { isLoading }] = useUpdateTicketMutation();
  const { ticket } = detail;
  const change = async (changes: { priority?: Priority; category?: Category }) => {
    try {
      await update({ ticketId: ticket.ticket_id, ...changes }).unwrap();
      notify.success("Ticket updated");
    } catch (error) {
      notify.apiError(error);
    }
  };

  return (
    <Card title="Ticket">
      <div className="mb-4 grid gap-3 sm:grid-cols-2">
        <Select aria-label="Priority" disabled={isLoading || ticket.status === "closed"} value={ticket.priority} options={toOptions(PRIORITY_LABELS)} onChange={(event) => void change({ priority: event.target.value as Priority })} />
        <Select aria-label="Category" disabled={isLoading || ticket.status === "closed"} value={ticket.category} options={toOptions(CATEGORY_LABELS)} onChange={(event) => void change({ category: event.target.value as Category })} />
      </div>
      <DescriptionList
        columns={1}
        items={[
          { label: "Student", value: detail.requester_name ?? `#${ticket.requester_user_id}` },
          { label: "Assignee", value: detail.assignee_name ?? "Unassigned" },
          { label: "Queue", value: QUEUE_LABELS[ticket.queue] },
          { label: "Source", value: ticket.source === "ai-tutor" ? "Handed off by the AI tutor" : "Opened by the student" },
          { label: "First response due", value: due(ticket.first_response_due_at, ticket.first_response_breached, ticket.first_response_at) },
          { label: "Resolution due", value: due(ticket.resolution_due_at, ticket.resolution_breached, ticket.resolved_at) },
          { label: "Reopened", value: ticket.reopened_count ? `${ticket.reopened_count}×` : "No" },
          { label: "Rating", value: ticket.csat_rating != null ? `${ticket.csat_rating} / 5` : ticket.csat_requested_at ? "Requested" : "—" },
          { label: "Opened", value: formatDateTime(ticket.created_at) },
        ]}
      />
    </Card>
  );
}
