import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { toApiError } from "@/core/lib/apiError";
import { toOptions } from "@/core/lib/options";
import { useNotify } from "@/core/hooks/useNotify";
import { useInterviewRights } from "@/modules/ai-interview/common/hooks/useInterviewRights";
import { DIFFICULTY_LABELS } from "@/modules/ai-interview/common/labels";
import type { Difficulty } from "@/modules/ai-interview/common/types";
import { useCreatePlanMutation, useGetPlanQuery, useUpdatePlanMutation } from "@/modules/ai-interview/plans/api/plansApi";
import { RoundsEditor } from "@/modules/ai-interview/plans/components/RoundsEditor";
import { emptyPlanForm, planToForm, toPlanBody, type PlanFormValues } from "@/modules/ai-interview/plans/form/planForm";
import { Alert, Button, Card, Field, Input, PageHeader, PageLoader, Select, Textarea } from "@/shared/ui";

const PROCTORING = [{ value: "none", label: "None" }, { value: "basic", label: "Basic" }, { value: "strict", label: "Strict" }];

export function PlanFormPage() {
  const { planId } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();
  const { planKind } = useInterviewRights();
  const { data: plan, isLoading } = useGetPlanQuery(planId ?? "", { skip: !planId });
  const [create, { isLoading: creating }] = useCreatePlanMutation();
  const [update, { isLoading: updating }] = useUpdatePlanMutation();
  const [v, setV] = useState<PlanFormValues>(emptyPlanForm);
  const [problems, setProblems] = useState<string[]>([]);

  useEffect(() => {
    if (plan) setV(planToForm(plan));
  }, [plan]);
  if (planId && isLoading) return <PageLoader />;
  const set = <K extends keyof PlanFormValues>(key: K, value: PlanFormValues[K]) => setV((c) => ({ ...c, [key]: value }));

  const save = async () => {
    setProblems([]);
    try {
      const body = toPlanBody(plan?.kind ?? planKind, v);
      const saved = planId ? await update({ id: planId, body }).unwrap() : await create(body).unwrap();
      notify.success("Plan saved");
      navigate(`/interviews/plans/${saved.plan_id}`, { replace: true });
    } catch (error) {
      const e = toApiError(error);
      setProblems(e.details.length ? e.details.map((d) => (d.field ? `${d.field}: ${d.message}` : d.message)) : [e.message]);
    }
  };

  return (
    <>
      <PageHeader title={planId ? `Edit ${plan?.title ?? "plan"}` : `New ${planKind === "mock" ? "practice" : "screening"} plan`} backTo={planId ? `/interviews/plans/${planId}` : "/interviews/plans"} backLabel="Plans" />
      <div className="space-y-4">
        {problems.length > 0 && <Alert tone="error" title="Please fix these"><ul className="list-disc pl-5">{problems.map((p) => <li key={p}>{p}</li>)}</ul></Alert>}
        <Card title="The interview">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Title" required>{(p) => <Input {...p} maxLength={160} value={v.title} onChange={(e) => set("title", e.target.value)} />}</Field>
            <Field label="Role" required>{(p) => <Input {...p} maxLength={120} value={v.role} placeholder="Backend developer" onChange={(e) => set("role", e.target.value)} />}</Field>
            <Field label="Skills" hint="Comma separated." className="sm:col-span-2">{(p) => <Input {...p} value={v.skills} onChange={(e) => set("skills", e.target.value)} />}</Field>
            <Field label="Level" hint="System design rounds need Senior.">{(p) => <Select {...p} value={v.difficulty} options={toOptions(DIFFICULTY_LABELS)} onChange={(e) => set("difficulty", e.target.value as Difficulty)} />}</Field>
            <Field label="Total minutes" required>{(p) => <Input {...p} type="number" min={5} value={v.duration_minutes} onChange={(e) => set("duration_minutes", e.target.value)} />}</Field>
            <Field label="Proctoring">{(p) => <Select {...p} value={v.proctoring_level} options={PROCTORING} onChange={(e) => set("proctoring_level", e.target.value)} />}</Field>
            <Field label="Attempts allowed">{(p) => <Input {...p} type="number" min={1} value={v.max_attempts} onChange={(e) => set("max_attempts", e.target.value)} />}</Field>
            <Field label="Instructions for the candidate" className="sm:col-span-2">{(p) => <Textarea {...p} rows={3} maxLength={2000} value={v.instructions} onChange={(e) => set("instructions", e.target.value)} />}</Field>
          </div>
        </Card>
        <Card title="Rounds"><RoundsEditor rounds={v.rounds} onChange={(rounds) => set("rounds", rounds)} /></Card>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => navigate(-1)}>Cancel</Button>
          <Button loading={creating || updating} onClick={() => void save()}>Save draft</Button>
        </div>
      </div>
    </>
  );
}
