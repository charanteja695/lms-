import { cn } from "@/core/lib/cn";
import type { MyApplication } from "@/modules/job-portal/applications/types";

const BAR = { done: "bg-brand-600", current: "bg-accent-500", upcoming: "bg-slate-200", stopped: "bg-slate-400" } as const;

/** The job's current and completed steps as a progress bar (upcoming pipeline roadmap stages are not shown to students). */
export function ProgressSteps({ steps }: { steps: MyApplication["progress"] }) {
  const visibleSteps = steps.filter((step) => step.state !== "upcoming");
  if (visibleSteps.length === 0) return null;

  return (
    <ol aria-label="Progress" className="grid gap-1.5" style={{ gridTemplateColumns: `repeat(${visibleSteps.length}, minmax(0, 1fr))` }}>
      {visibleSteps.map((step) => (
        <li key={step.key} className="flex min-w-0 flex-col gap-1.5" aria-current={step.state === "current" ? "step" : undefined}>
          <span className={cn("h-1.5 rounded-full", BAR[step.state])} />
          <span className={cn("truncate text-xs", step.state === "current" ? "font-extrabold text-navy-950" : "font-semibold text-slate-700")}>
            {step.state === "stopped" ? `Stopped · ${step.label}` : step.label}
          </span>
        </li>
      ))}
    </ol>
  );
}
