import { Link } from "react-router-dom";

import { cn } from "@/core/lib/cn";
import { missingText } from "@/modules/catalog/builder/hooks/useBuildIssues";
import type { CourseTest } from "@/modules/catalog/builder/hooks/useCourseTests";
import { Icon } from "@/shared/ui";

/**
 * The test that closes a topic (or the course). Shows what it holds against what it needs, as assessment-service
 * reports it, and links to its editor.
 */
export function TestGate({ test, to, label, needMcq, needPrograms, editable, dark = false }: {
  test: CourseTest | undefined;
  to: string;
  label: string;
  needMcq: number;
  needPrograms: number;
  editable: boolean;
  dark?: boolean;
}) {
  const composition = test?.composition;
  const complete = Boolean(composition?.valid);
  const published = test?.test.status === "published";
  const missing = missingText(test, needMcq, needPrograms);

  const summary = !test
    ? `Needs at least ${needMcq} multiple-choice and ${needPrograms} ${needPrograms === 1 ? "program" : "programs"}.`
    : composition
      ? `${composition.multiple_choice} multiple-choice · ${composition.programs} ${composition.programs === 1 ? "program" : "programs"} · pass mark ${test.test.pass_mark_percent}%`
      : "Checking…";
  const state = !test ? null : published ? "Published" : complete ? "Ready to publish" : missing ? `Needs ${missing}` : "Has problems";

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-3 rounded-xl p-3",
        dark ? "bg-ink-900 text-white" : "bg-white ring-1",
        !dark && (published ? "ring-brand-200" : test && complete ? "ring-navy-200" : "ring-amber-300"),
      )}
    >
      <span className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg", dark ? "bg-white/10" : "bg-navy-950 text-white")}>
        <Icon name="clipboardCheck" size={17} />
      </span>
      <div className="min-w-0 flex-1 basis-56">
        <p className={cn("text-sm font-bold", dark ? "text-white" : "text-navy-950")}>{label}</p>
        <p className={cn("text-xs", dark ? "text-slate-300" : "text-slate-600")}>{summary}</p>
      </div>
      {state && (
        <span className={cn("rounded-full px-2.5 py-1 text-xs font-bold", published ? "bg-brand-50 text-brand-800" : complete ? "bg-navy-50 text-navy-800" : "bg-amber-100 text-amber-900")}>{state}</span>
      )}
      {(editable || test) && (
        <Link
          to={to}
          className={cn(
            "inline-flex h-9 items-center rounded-lg px-3.5 text-sm font-bold transition-colors",
            !test || !complete ? "bg-brand-700 text-white hover:bg-brand-800" : dark ? "bg-white text-navy-950 hover:bg-slate-100" : "bg-white text-navy-950 ring-1 ring-slate-300 hover:bg-slate-50",
          )}
        >
          {!test ? "Create test" : editable && !published ? "Edit test" : "Open test"}
        </Link>
      )}
    </div>
  );
}
