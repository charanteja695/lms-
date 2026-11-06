import type { CaseReport } from "@/modules/proctoring/cases/types";
import { Badge, Card } from "@/shared/ui";

const AI_ANALYSIS_LABELS: Record<string, string> = {
  complete: "Complete", partial: "Partial", unavailable: "Unavailable", not_applicable: "Not applicable (basic level)", pending: "Pending",
};

function CountList({ counts }: { counts: Record<string, number> }) {
  const entries = Object.entries(counts);
  if (entries.length === 0) return <p className="text-sm text-slate-500">None.</p>;
  return (
    <ul className="space-y-1 text-sm">
      {entries.map(([key, value]) => (
        <li key={key} className="flex items-center justify-between">
          <span className="text-slate-600">{key.replace(/_/g, " ")}</span>
          <span className="font-medium text-slate-900">{value}</span>
        </li>
      ))}
    </ul>
  );
}

export function CaseReportCard({ report }: { report: CaseReport }) {
  return (
    <Card title="Risk report">
      <div className="grid gap-6 sm:grid-cols-2">
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Risk breakdown</p>
          <CountList counts={report.risk_breakdown} />
        </div>
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Event counts</p>
          <CountList counts={report.event_counts} />
        </div>
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Snapshots</p>
          <CountList counts={report.snapshots} />
        </div>
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">AI analysis</p>
          <Badge tone={report.ai_analysis === "complete" ? "green" : report.ai_analysis === "unavailable" ? "amber" : "gray"}>
            {AI_ANALYSIS_LABELS[report.ai_analysis] ?? report.ai_analysis}
          </Badge>
        </div>
      </div>
    </Card>
  );
}
