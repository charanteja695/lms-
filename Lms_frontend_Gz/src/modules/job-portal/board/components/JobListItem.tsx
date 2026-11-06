import { cn } from "@/core/lib/cn";
import { formatDate } from "@/core/lib/format";
import { CompanyMark } from "@/modules/job-portal/board/components/CompanyMark";
import type { CandidateJob } from "@/modules/job-portal/board/types";
import { ctcRange, stipendLabel } from "@/modules/job-portal/common/format";
import { EMPLOYMENT_LABELS, LOCATION_TYPE_LABELS } from "@/modules/job-portal/common/labels";
import { Icon } from "@/shared/ui";

/** One job in the list: who, what, where, pay, and eligibility status with clean hierarchy. */
export function JobListItem({
  job,
  selected,
  onSelect,
}: {
  job: CandidateJob;
  selected: boolean;
  onSelect: () => void;
}) {
  const score = job.match?.score;
  const pay = job.employment_type === "internship" ? stipendLabel(job) : ctcRange(job);
  const locationText = [
    LOCATION_TYPE_LABELS[job.location_type],
    job.location_type !== "remote" && job.locations?.length > 0 ? job.locations[0] : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={selected ? "true" : undefined}
      className={cn(
        "group relative flex w-full flex-col justify-between rounded-xl border bg-white p-4 text-left transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
        selected
          ? "border-brand-600 bg-blue-50/25 shadow-sm ring-1 ring-brand-600"
          : "border-slate-200/80 hover:border-slate-300 hover:bg-slate-50/50 hover:shadow-sm"
      )}
    >
      {/* Top row: Company Mark + Title & Company + Match Score */}
      <div className="flex w-full items-start gap-3">
        <CompanyMark name={job.company_name} size="md" />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <h3
              className={cn(
                "truncate text-[15px] font-semibold leading-tight transition-colors",
                selected ? "font-bold text-brand-900" : "text-slate-900 group-hover:text-brand-600"
              )}
              title={job.title}
            >
              {job.title}
            </h3>
            {score != null && (
              <span
                className={cn(
                  "shrink-0 inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold tracking-tight",
                  score >= 75
                    ? "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200"
                    : score >= 50
                    ? "bg-amber-50 text-amber-700 ring-1 ring-amber-200"
                    : "bg-slate-100 text-slate-600 ring-1 ring-slate-200"
                )}
              >
                {score}% match
              </span>
            )}
          </div>
          <p className="mt-0.5 truncate text-xs font-medium text-slate-500">
            {job.company_name ?? "Company"}
          </p>
        </div>
      </div>

      {/* Middle row: Job Type, Work Mode & Location, Pay */}
      <div className="mt-2.5 flex flex-wrap items-center gap-1.5 text-xs text-slate-600">
        <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700">
          <Icon name="briefcase" size={11} className="text-slate-400" />
          {EMPLOYMENT_LABELS[job.employment_type]}
        </span>
        {locationText && (
          <span
            className="inline-flex max-w-[170px] items-center gap-1 truncate rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700"
            title={locationText}
          >
            <Icon name="map" size={11} className="shrink-0 text-slate-400" />
            <span className="truncate">{locationText}</span>
          </span>
        )}
        {pay && (
          <span className="inline-flex items-center rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700">
            {pay}
          </span>
        )}
      </div>

      {/* Bottom row: Deadline + Eligibility / Applied Status */}
      <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-2.5 text-xs">
        <span className="truncate text-[11px] text-slate-400">
          {job.deadline_at ? `Deadline: ${formatDate(job.deadline_at)}` : "Open application"}
        </span>

        <div className="shrink-0">
          {job.applied ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-0.5 text-[11px] font-semibold text-blue-700 ring-1 ring-inset ring-blue-200">
              <Icon name="check" size={11} /> Applied
            </span>
          ) : job.eligibility_result?.eligible === true ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200">
              <Icon name="check" size={11} /> Eligible
            </span>
          ) : job.eligibility_result?.eligible === false ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
              Not eligible
            </span>
          ) : null}
        </div>
      </div>
    </button>
  );
}
