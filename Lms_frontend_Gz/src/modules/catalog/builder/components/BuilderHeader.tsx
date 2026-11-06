import { Link } from "react-router-dom";

import { cn } from "@/core/lib/cn";
import { ContentStatusBadge } from "@/modules/catalog/common/components/ContentStatusBadge";
import type { ContentStatus } from "@/modules/catalog/common/types";
import { Icon } from "@/shared/ui";

export type BuilderStep = "details" | "curriculum" | "final" | "publish";

/** The course name, its status and the four steps: details, curriculum, final test, review and publish. */
export function BuilderHeader({ courseId, versionId, title, status, step, done }: {
  courseId: string;
  versionId: string;
  title: string;
  status: ContentStatus;
  step: BuilderStep;
  /** Which steps have nothing left to do. */
  done: Partial<Record<BuilderStep, boolean>>;
}) {
  const base = `/courses/${courseId}/versions/${versionId}`;
  const steps: Array<{ key: BuilderStep; label: string; to: string }> = [
    { key: "details", label: "Details", to: `/courses/${courseId}/edit` },
    { key: "curriculum", label: "Curriculum", to: base },
    { key: "final", label: "Final test", to: `${base}/final-test` },
    { key: "publish", label: "Review & publish", to: `${base}/publish` },
  ];

  return (
    <header className="mb-6 space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/courses" aria-label="Back to courses" className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-slate-600 shadow-card ring-1 ring-slate-200/60 hover:text-navy-950">
          <Icon name="chevronLeft" size={18} />
        </Link>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="truncate text-2xl font-extrabold tracking-tight text-navy-950">{title}</h1>
            <ContentStatusBadge status={status} />
          </div>
          <p className="text-[13px] text-slate-500">Every change saves as you make it.</p>
        </div>
      </div>
      <nav aria-label="Course steps" className="flex flex-wrap gap-1 border-b border-slate-200">
        {steps.map((item, index) => {
          const current = item.key === step;
          const complete = done[item.key];
          return (
            <Link
              key={item.key}
              to={item.to}
              aria-current={current ? "step" : undefined}
              className={cn("flex h-11 items-center gap-2 px-3 text-sm transition-colors", current ? "font-extrabold text-navy-950 shadow-[inset_0_-3px_0_var(--color-brand-600)]" : "font-semibold text-slate-600 hover:text-navy-950")}
            >
              <span className={cn("flex h-6 w-6 items-center justify-center rounded-full text-xs font-extrabold", complete ? "bg-brand-600 text-white" : current ? "bg-navy-950 text-white" : "bg-slate-200 text-slate-700")}>
                {complete ? <Icon name="check" size={13} /> : index + 1}
              </span>
              {item.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
