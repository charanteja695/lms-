import { formatDateTime } from "@/core/lib/format";
import { APPLICATION_STATUS_LABELS } from "@/modules/job-portal/common/labels";
import type { StageEntry } from "@/modules/job-portal/common/types";

/** An application's moves through the pipeline, oldest first. */
export function StageHistory({ history }: { history: StageEntry[] }) {
  if (history.length === 0) return <p className="text-sm text-slate-500">No history yet.</p>;
  return (
    <ol className="relative space-y-3 border-l border-slate-200 pl-4">
      {history.map((entry, index) => (
        <li key={index} className="text-sm">
          <span className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border-2 border-white bg-brand-600" />
          <p className="font-medium text-slate-900">{APPLICATION_STATUS_LABELS[entry.to_status] ?? entry.to_status}</p>
          <p className="text-xs text-slate-500">{formatDateTime(entry.created_at)} · {entry.actor}</p>
          {entry.note && <p className="mt-0.5 text-slate-600">{entry.note}</p>}
        </li>
      ))}
    </ol>
  );
}
