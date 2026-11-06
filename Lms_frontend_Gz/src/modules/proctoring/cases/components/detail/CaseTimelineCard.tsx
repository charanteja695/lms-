import { formatDateTime } from "@/core/lib/format";
import type { TimelineEntry } from "@/modules/proctoring/cases/types";
import { Badge, Card } from "@/shared/ui";

const SOURCE_TONES = { client: "gray", ai: "purple", system: "blue", staff: "amber" } as const;

export function CaseTimelineCard({ timeline }: { timeline: TimelineEntry[] }) {
  return (
    <Card title={`Timeline (${timeline.length})`}>
      {timeline.length === 0 ? (
        <p className="text-sm text-slate-500">No events recorded.</p>
      ) : (
        <ul className="max-h-96 space-y-2 overflow-y-auto text-sm">
          {timeline.map((entry, index) => (
            <li key={index} className="flex items-center justify-between gap-3 border-b border-slate-100 pb-2 last:border-0">
              <span className="flex items-center gap-2">
                <Badge tone={SOURCE_TONES[entry.source]}>{entry.source}</Badge>
                {entry.type.replace(/_/g, " ")}
                {entry.points > 0 && <span className="text-xs text-slate-500">+{entry.points}</span>}
              </span>
              <span className="shrink-0 text-xs text-slate-500">{formatDateTime(entry.at)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
