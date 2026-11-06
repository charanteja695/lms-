import { formatDateTime } from "@/core/lib/format";
import { useGetAttemptEventsQuery } from "@/modules/assessments/attempts/api/attemptsApi";
import { Card, EmptyState } from "@/shared/ui";

export function AttemptEventsCard({ attemptId }: { attemptId: string }) {
  const { data: events, isFetching } = useGetAttemptEventsQuery(attemptId);

  return (
    <Card title="Audit trail">
      {!isFetching && (events?.length ?? 0) === 0 ? (
        <EmptyState icon="clock" title="No events recorded" description="Events such as starts, pauses and submissions appear here as they happen." />
      ) : (
        <ul className="divide-y divide-slate-100">
          {events?.map((event, index) => (
            <li key={index} className="flex items-center justify-between gap-3 py-2 text-sm">
              <span className="text-slate-700" title={event.event_type}>{event.event_type.charAt(0).toUpperCase() + event.event_type.slice(1).replaceAll("_", " ")}</span>
              <span className="text-xs text-slate-500">{formatDateTime(event.created_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
