import { formatDateTime } from "@/core/lib/format";
import { useGetDownvotedQuery, useGetFeedbackSummaryQuery } from "@/modules/ai-tutor/insights/api/insightsApi";
import { Card, EmptyState, Spinner, StatTile } from "@/shared/ui";

/** Thumbs up/down totals for a course and the answers students marked unhelpful (the server never says who asked). */
export function FeedbackPanel({ courseId }: { courseId: string }) {
  const { data: summary } = useGetFeedbackSummaryQuery(courseId);
  const { data: downvoted = [], isLoading } = useGetDownvotedQuery(courseId);

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatTile icon="check" label="Helpful" value={summary?.up ?? "—"} />
        <StatTile icon="x" label="Not helpful" value={summary?.down ?? "—"} />
        <StatTile icon="alert" label="Unhelpful rate" value={summary?.down_rate != null ? `${(summary.down_rate * 100).toFixed(1)}%` : "—"} />
      </div>
      <Card title="Answers marked unhelpful">
        {isLoading ? (
          <Spinner />
        ) : downvoted.length === 0 ? (
          <EmptyState icon="check" title="No unhelpful answers" description="When students mark a tutor answer as unhelpful, it shows up here to review." />
        ) : (
          <ul className="space-y-4">
            {downvoted.map((item) => (
              <li key={item.message_id} className="space-y-1 border-b border-slate-100 pb-4 text-sm last:border-0 last:pb-0">
                <p className="font-medium text-slate-900">{item.question ?? "(question not kept)"}</p>
                <p className="whitespace-pre-wrap text-slate-600">{item.answer}</p>
                {item.comment && <p className="text-amber-700">Student said: {item.comment}</p>}
                <p className="text-xs text-slate-400">{formatDateTime(item.at)}</p>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
