import { useNotify } from "@/core/hooks/useNotify";
import { RecommendationBadge } from "@/modules/ai-interview/common/components/InterviewBadges";
import { useReEvaluateMutation, type Evaluation } from "@/modules/ai-interview/screening/api/screeningApi";
import { Alert, Badge, Button, Card } from "@/shared/ui";

/** The AI's rubric scores, each backed by quotes the server verified against the transcript; a recommendation, never a decision. */
export function EvaluationCard({ interviewId, evaluation }: { interviewId: string; evaluation: Evaluation | null }) {
  const notify = useNotify();
  const [reEvaluate, { isLoading }] = useReEvaluateMutation();
  const retry = <Button size="sm" variant="secondary" loading={isLoading} onClick={() => void reEvaluate(interviewId).unwrap().then(() => notify.success("Re-evaluation queued"), notify.apiError)}>Re-evaluate</Button>;

  if (!evaluation) return <Card title="AI evaluation" actions={retry}><p className="text-sm text-slate-500">Not evaluated yet.</p></Card>;

  return (
    <Card title="AI evaluation" description={`${evaluation.model ?? "model"} · prompt v${evaluation.prompt_version ?? "?"}`} actions={retry}>
      <div className="space-y-3 text-sm">
        {evaluation.status === "failed" && <Alert tone="error" title="Evaluation failed">{evaluation.last_error}</Alert>}
        <p className="flex items-center gap-2">AI suggests <RecommendationBadge value={evaluation.recommendation} />{evaluation.overall_score != null && <span className="text-slate-600">· overall {evaluation.overall_score.toFixed(1)} / 5</span>}</p>
        {evaluation.summary && <p className="whitespace-pre-wrap text-slate-700">{evaluation.summary}</p>}
        <ul className="space-y-1">
          {Object.entries(evaluation.criterion_scores).map(([c, s]) => (
            <li key={c} className="flex justify-between"><span className="capitalize">{c.replace(/_/g, " ")}</span><span className="font-medium">{s} / 5</span></li>
          ))}
        </ul>
        {evaluation.flags.length > 0 && <div className="flex flex-wrap gap-1">{evaluation.flags.map((f) => <Badge key={f} tone="amber">{f}</Badge>)}</div>}
        <p className="text-xs text-slate-500">{evaluation.total_quotes - evaluation.invalid_quotes} of {evaluation.total_quotes} quoted evidence lines found in the transcript.</p>
      </div>
    </Card>
  );
}
