import { formatDateTime } from "@/core/lib/format";
import type { EvalRun } from "@/modules/ai-tutor/insights/types";
import { Badge, Card } from "@/shared/ui";

/** One run's scores (hit rate at k and MRR, as computed by the server) and each question's outcome. */
export function EvalRunCard({ run }: { run: EvalRun }) {
  return (
    <Card
      title={`Hit rate ${(run.hit_rate * 100).toFixed(1)}% · MRR ${run.mrr.toFixed(3)}`}
      description={`${run.hits} of ${run.case_count} found in the top ${run.top_k} · version #${run.version_id} · ${formatDateTime(run.created_at)}`}
      actions={<Badge tone={run.method === "dense" ? "green" : "amber"}>{run.method === "dense" ? "Embeddings" : "Word match (embeddings unavailable)"}</Badge>}
    >
      <ul className="space-y-2 text-sm">
        {run.results.map((result, index) => (
          <li key={index} className="flex items-start justify-between gap-3 border-b border-slate-100 pb-2 last:border-0">
            <span className="text-slate-700">{result.question}</span>
            <span className="shrink-0">
              {result.hit ? <Badge tone="green">Found{result.rank != null ? ` at #${result.rank}` : ""}</Badge> : <Badge tone="red">Missed</Badge>}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
