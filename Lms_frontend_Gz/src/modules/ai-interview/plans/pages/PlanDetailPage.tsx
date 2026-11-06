import { useNavigate, useParams } from "react-router-dom";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { PlanStatusBadge } from "@/modules/ai-interview/common/components/InterviewBadges";
import { DIFFICULTY_LABELS, ROUND_LABELS } from "@/modules/ai-interview/common/labels";
import { useGetPlanQuery, usePlanActionMutation } from "@/modules/ai-interview/plans/api/plansApi";
import { CalibrationCard } from "@/modules/ai-interview/plans/components/CalibrationCard";
import { FairnessAuditCard } from "@/modules/ai-interview/plans/components/FairnessAuditCard";
import { Badge, Button, Card, ConfirmDialog, EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function PlanDetailPage() {
  const { planId = "" } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();
  const confirm = useConfirmAction();
  const { data: plan, isLoading, isError } = useGetPlanQuery(planId);
  const [act, { isLoading: acting }] = usePlanActionMutation();

  if (isLoading) return <PageLoader />;
  if (isError || !plan) return <EmptyState icon="alert" title="Plan not found" />;
  const run = (action: "publish" | "retire" | "versions", message: string) =>
    void act({ id: planId, action }).unwrap().then((next) => {
      notify.success(message);
      if (action === "versions") navigate(`/interviews/plans/${next.plan_id}/edit`);
    }, notify.apiError);

  return (
    <>
      <PageHeader
        title={plan.title}
        description={<span className="flex items-center gap-2"><PlanStatusBadge status={plan.status} /> {plan.role} · v{plan.version} · {DIFFICULTY_LABELS[plan.difficulty]} · {plan.duration_minutes} min</span>}
        backTo="/interviews/plans"
        backLabel="Plans"
        actions={
          <div className="flex gap-2">
            {plan.status === "draft" && <Button variant="secondary" icon="edit" onClick={() => navigate(`/interviews/plans/${planId}/edit`)}>Edit</Button>}
            {plan.status === "draft" && (
              <Button loading={acting} onClick={() => confirm.ask({ title: "Publish this plan?", description: "It's frozen once published; the family's previous version is retired.", confirmLabel: "Publish", tone: "primary" }, async () => run("publish", "Published"))}>Publish</Button>
            )}
            {plan.status === "published" && <Button variant="secondary" loading={acting} onClick={() => run("versions", "New draft version")}>New version</Button>}
            {plan.status === "published" && <Button variant="danger" loading={acting} onClick={() => confirm.ask({ title: "Retire this plan?", description: "No new interviews can use it.", confirmLabel: "Retire" }, async () => run("retire", "Retired"))}>Retire</Button>}
          </div>
        }
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Rounds" className="lg:col-span-2">
          <ol className="space-y-3">
            {plan.rounds.map((r, i) => (
              <li key={i} className="text-sm">
                <p className="font-medium text-slate-900">{i + 1}. {ROUND_LABELS[r.type]} · {r.minutes} min {r.languages.length > 0 && <span className="font-normal text-slate-500">({r.languages.join(", ")})</span>}</p>
                <ul className="mt-1 list-disc pl-5 text-slate-700">{r.questions.map((q) => <li key={q}>{q}</li>)}</ul>
                <div className="mt-1 flex flex-wrap gap-1">{r.criteria.map((c) => <Badge key={c}>{c.replace(/_/g, " ")}</Badge>)}</div>
              </li>
            ))}
          </ol>
        </Card>
        {plan.kind === "screening" && plan.status !== "draft" && <CalibrationCard planId={planId} />}
        {plan.kind === "screening" && plan.status !== "draft" && <FairnessAuditCard planId={planId} />}
      </div>
      <ConfirmDialog {...confirm.dialogProps} />
    </>
  );
}
