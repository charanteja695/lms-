import { APPLICATION_STATUS_LABELS } from "@/modules/job-portal/common/labels";
import type { ApplicationStatus } from "@/modules/job-portal/common/types";
import { useGetFunnelQuery, useListScreeningDecisionsQuery } from "@/modules/job-portal/employer/api/pipelineApi";
import { formatDateTime } from "@/core/lib/format";
import { Card, Spinner, StatTile } from "@/shared/ui";

/** Where applicants are, as counted by the server, and the AI screening audit log (model, prompt version, input digest). */
export function FunnelTab({ jobId }: { jobId: string }) {
  const { data: funnel } = useGetFunnelQuery(jobId);
  const { data: decisions = [], isFetching } = useListScreeningDecisionsQuery({ jobId, per_page: 50 });
  if (!funnel) return <Spinner />;
  const max = Math.max(1, ...Object.values(funnel.by_status));

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatTile icon="users" label="Applicants" value={funnel.total} />
        <StatTile icon="check" label="Placed" value={funnel.placed} />
        <StatTile icon="briefcase" label="Openings" value={funnel.openings} />
      </div>
      <Card title="By stage">
        <ul className="space-y-1.5 text-sm">
          {Object.entries(funnel.by_status).map(([status, count]) => (
            <li key={status}>
              <div className="flex justify-between"><span>{APPLICATION_STATUS_LABELS[status as ApplicationStatus] ?? status}</span><span className="font-medium">{count}</span></div>
              <div className="h-1.5 rounded bg-slate-100"><div className="h-1.5 rounded bg-brand-600" style={{ width: `${(100 * count) / max}%` }} /></div>
            </li>
          ))}
        </ul>
      </Card>
      <Card title="AI screening audit" description="Every recommendation, with what produced it.">
        {isFetching ? <Spinner /> : decisions.length === 0 ? <p className="text-sm text-slate-500">No screening yet.</p> : (
          <ul className="max-h-80 space-y-2 overflow-y-auto text-xs">
            {decisions.map((d, index) => (
              <li key={index} className="border-b border-slate-100 pb-2 last:border-0">
                <span className="font-medium text-slate-800">{d.recommendation}</span>{d.score != null && ` · ${d.score}`} · {d.source}
                {d.model && ` · ${d.model}`}{d.prompt_version != null && ` · prompt v${d.prompt_version}`}
                <span className="block text-slate-400">{formatDateTime(d.created_at)} · input {d.input_digest.slice(0, 12)}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
