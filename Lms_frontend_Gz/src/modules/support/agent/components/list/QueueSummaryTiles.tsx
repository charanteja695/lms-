import { QUEUE_LABELS } from "@/modules/support/common/labels";
import { useGetQueueSummaryQuery } from "@/modules/support/agent/api/agentTicketsApi";
import { Card } from "@/shared/ui";

function minutesLabel(minutes: number | null): string {
  if (minutes == null) return "—";
  if (minutes < 60) return `${Math.round(minutes)} min`;
  if (minutes < 60 * 24) return `${(minutes / 60).toFixed(1)} h`;
  return `${(minutes / 60 / 24).toFixed(1)} d`;
}

/** One card per queue this agent can see, with the server's counts. */
export function QueueSummaryTiles() {
  const { data: queues = [] } = useGetQueueSummaryQuery();
  if (queues.length === 0) return null;
  return (
    <div className="mb-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {queues.map((queue) => (
        <Card key={queue.queue} title={QUEUE_LABELS[queue.queue]}>
          <dl className="grid grid-cols-3 gap-3 text-center">
            {[
              ["Open", queue.open],
              ["Unassigned", queue.unassigned],
              ["Waiting", queue.waiting_on_student],
              ["Assigned", queue.assigned],
              ["Breached", queue.breached],
              ["Oldest unanswered", minutesLabel(queue.oldest_unanswered_minutes)],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-xs text-slate-500">{label}</dt>
                <dd className={label === "Breached" && Number(value) > 0 ? "text-lg font-semibold text-red-600" : "text-lg font-semibold text-slate-900"}>{value}</dd>
              </div>
            ))}
          </dl>
        </Card>
      ))}
    </div>
  );
}
