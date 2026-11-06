import { formatDateTime } from "@/core/lib/format";
import { useGetTicketEventsQuery } from "@/modules/support/agent/api/agentTicketsApi";
import { UserNameCell } from "@/modules/user-management/common/components/UserNameCell";
import { Badge, Card } from "@/shared/ui";

export function TicketEventsCard({ ticketId }: { ticketId: string }) {
  const { data: events = [] } = useGetTicketEventsQuery(ticketId);
  return (
    <Card title="Audit trail">
      {events.length === 0 ? (
        <p className="text-sm text-slate-500">No events.</p>
      ) : (
        <ul className="max-h-80 space-y-2 overflow-y-auto text-sm">
          {events.map((event, index) => (
            <li key={index} className="flex items-start justify-between gap-3 border-b border-slate-100 pb-2 last:border-0">
              <span className="flex flex-wrap items-center gap-2">
                <Badge tone={event.event_type.includes("breach") ? "red" : "gray"}>{event.event_type.replace(/[._]/g, " ")}</Badge>
                {event.actor_user_id && <UserNameCell userId={event.actor_user_id} />}
              </span>
              <span className="shrink-0 text-xs text-slate-500">{formatDateTime(event.created_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
