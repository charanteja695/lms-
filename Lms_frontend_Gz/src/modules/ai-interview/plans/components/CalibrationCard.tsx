import { useNotify } from "@/core/hooks/useNotify";
import { formatDateTime } from "@/core/lib/format";
import { useListCalibrationRunsQuery, useListCalibrationSamplesQuery, useRunCalibrationMutation } from "@/modules/ai-interview/plans/api/plansApi";
import { Button, Card } from "@/shared/ui";

const pct = (v: number | null) => (v == null ? "—" : `${(v * 100).toFixed(0)}%`);

/** How closely the AI's scores agree with people's ratings of the same transcripts. Samples are added from a reviewed interview. */
export function CalibrationCard({ planId }: { planId: string }) {
  const notify = useNotify();
  const { data: samples = [] } = useListCalibrationSamplesQuery(planId);
  const { data: runs = [] } = useListCalibrationRunsQuery(planId);
  const [run, { isLoading }] = useRunCalibrationMutation();

  return (
    <Card
      title="Calibration"
      description={`${samples.length} human-rated sample${samples.length === 1 ? "" : "s"}. Add one from a reviewed screening interview.`}
      actions={<Button size="sm" variant="secondary" loading={isLoading} disabled={samples.length === 0} onClick={() => void run(planId).unwrap().then(() => notify.success("Calibration run finished"), notify.apiError)}>Run</Button>}
    >
      {runs.length === 0 ? (
        <p className="text-sm text-slate-500">No runs yet.</p>
      ) : (
        <ul className="divide-y divide-slate-100 text-sm">
          {runs.map((r) => (
            <li key={r.run_id} className="py-2">
              <p className="text-slate-800">Within one point {pct(r.within_one_rate)} · recommendation agreement {pct(r.recommendation_agreement)} · mean error {r.mean_abs_error?.toFixed(2) ?? "—"}</p>
              <p className="text-xs text-slate-500">{r.samples} samples · {r.model ?? "model"} prompt v{r.prompt_version ?? "?"} · {formatDateTime(r.created_at)}</p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
