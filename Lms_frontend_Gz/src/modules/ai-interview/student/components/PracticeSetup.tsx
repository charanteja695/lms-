import { useInterviewRights } from "@/modules/ai-interview/common/hooks/useInterviewRights";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { cn } from "@/core/lib/cn";
import { DIFFICULTY_LABELS, ROUND_LABELS } from "@/modules/ai-interview/common/labels";
import type { Plan } from "@/modules/ai-interview/common/types";
import { useStartMockMutation } from "@/modules/ai-interview/student/api/studentInterviewsApi";
import { Button, EmptyState } from "@/shared/ui";

/** Set up a practice interview in one place: pick a role, then one of the interviews published for it, then start. */
export function PracticeSetup({ plans }: { plans: Plan[] }) {
  const navigate = useNavigate();
  const notify = useNotify();
  const roles = [...new Set(plans.map((p) => p.role))];
  const [role, setRole] = useState(roles[0] ?? "");
  const forRole = plans.filter((p) => p.role === role);
  const [planId, setPlanId] = useState<string | null>(null);
  const plan = forRole.find((p) => p.plan_id === planId) ?? forRole[0];
  const { canStart } = useInterviewRights();
  const [start, { isLoading }] = useStartMockMutation();

  if (plans.length === 0) return <EmptyState icon="helpCircle" title="No practice interviews yet" description="They appear here once the careers team publishes them." />;

  return (
    <section aria-labelledby="practise" className="space-y-5 rounded-2xl bg-white p-5 shadow-card ring-1 ring-slate-200/60 sm:p-6">
      <h2 id="practise" className="text-lg font-extrabold text-navy-950">Practice interview</h2>
      <div className="space-y-2">
        <p className="text-sm font-semibold text-navy-950">Role</p>
        <div className="flex flex-wrap gap-2">
          {roles.map((r) => (
            <button
              key={r}
              type="button"
              aria-pressed={r === role}
              onClick={() => { setRole(r); setPlanId(null); }}
              className={cn("min-h-[44px] rounded-full px-4 text-sm font-semibold", r === role ? "bg-brand-50 text-brand-800 ring-1 ring-brand-500" : "text-slate-600 ring-1 ring-slate-200 hover:text-navy-950")}
            >
              {r}
            </button>
          ))}
        </div>
      </div>
      <div className="space-y-2">
        <p className="text-sm font-semibold text-navy-950">Interview</p>
        <div role="radiogroup" className="grid gap-2 sm:grid-cols-2">
          {forRole.map((p) => {
            const on = p.plan_id === plan?.plan_id;
            return (
              <button
                key={p.plan_id}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => setPlanId(p.plan_id)}
                className={cn("flex flex-col items-start gap-1 rounded-xl px-4 py-3 text-left", on ? "bg-brand-50/60 ring-2 ring-brand-600" : "ring-1 ring-slate-200 hover:ring-brand-300")}
              >
                <span className="text-sm font-bold text-navy-950">{p.title}</span>
                <span className="text-xs text-slate-500">{p.duration_minutes} min · {DIFFICULTY_LABELS[p.difficulty]} · {p.rounds.map((r) => ROUND_LABELS[r.type]).join(", ")}</span>
              </button>
            );
          })}
        </div>
      </div>
      {plan?.instructions && <p className="rounded-xl bg-slate-50 p-3 text-[13px] text-slate-600">{plan.instructions}</p>}
      <Button
        size="lg"
        fullWidth
        loading={isLoading}
        disabled={!plan || !canStart}
        onClick={async () => {
          if (!plan) return;
          try {
            const created = await start(plan.plan_id).unwrap();
            navigate(`/interviews/mine/${created.interview_id}`);
          } catch (error) {
            notify.apiError(error, "Couldn't start");
          }
        }}
      >
        Start {plan ? `${plan.duration_minutes}-minute interview` : "interview"}
      </Button>
      <p className="text-center text-xs text-slate-500">You'll accept the consent and check your microphone on the next screen. The timer starts when you press Start there.</p>
    </section>
  );
}
