import { cn } from "@/core/lib/cn";
import { formatDate } from "@/core/lib/format";
import { ApplyBox } from "@/modules/job-portal/board/components/ApplyBox";
import { CompanyMark } from "@/modules/job-portal/board/components/CompanyMark";
import type { CandidateJob } from "@/modules/job-portal/board/types";
import { ctcRange, experienceLabel, stipendLabel } from "@/modules/job-portal/common/format";
import { EMPLOYMENT_LABELS, LOCATION_TYPE_LABELS } from "@/modules/job-portal/common/labels";
import { Badge, Icon } from "@/shared/ui";

/** A job in full for the student: organized sections, eligibility, description, qualifications, and applying. */
export function JobPanel({ job }: { job: CandidateJob }) {
  const eligibility = job.eligibility_result;
  const pay = job.employment_type === "internship" ? stipendLabel(job) : ctcRange(job);
  const locationString = job.locations && job.locations.length > 0 ? job.locations.join(", ") : null;

  return (
    <article className="space-y-6 rounded-2xl border border-slate-200/80 bg-white p-6 shadow-sm">
      {/* 0. Notice Banner (Optional) */}
      {job.banner_text && (
        <div
          className={cn(
            "flex items-center gap-2 rounded-xl border px-3.5 py-2.5 text-xs font-medium",
            job.banner_type === "warning"
              ? "border-amber-200 bg-amber-50 text-amber-900"
              : "border-sky-200 bg-sky-50 text-sky-900"
          )}
        >
          <Icon
            name={job.banner_type === "warning" ? "alert" : "info"}
            size={14}
            className="shrink-0"
          />
          <span>{job.banner_text}</span>
        </div>
      )}

      {/* 1. Job Header */}
      <header className="space-y-4 border-b border-slate-100 pb-5">
        <div className="flex items-start gap-4">
          <CompanyMark name={job.company_name} size="lg" />
          <div className="min-w-0 flex-1">
            <h1 className="text-xl font-bold leading-tight tracking-tight text-slate-900 sm:text-2xl">
              {job.title}
            </h1>
            <p className="mt-1 text-sm font-semibold text-slate-600">
              {job.company_name ?? "Company"}
            </p>
          </div>
        </div>

        {/* Header Metadata Chips */}
        <div className="flex flex-wrap items-center gap-2 pt-1 text-xs">
          <span className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-2.5 py-1 font-medium text-slate-700">
            <Icon name="briefcase" size={13} className="text-slate-400" />
            {EMPLOYMENT_LABELS[job.employment_type]}
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-2.5 py-1 font-medium text-slate-700">
            <Icon name="monitor" size={13} className="text-slate-400" />
            {LOCATION_TYPE_LABELS[job.location_type]}
          </span>
          {locationString && (
            <span className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-2.5 py-1 font-medium text-slate-700">
              <Icon name="map" size={13} className="text-slate-400" />
              {locationString}
            </span>
          )}
          {pay && (
            <span className="inline-flex items-center gap-1.5 rounded-lg bg-blue-50 px-2.5 py-1 font-semibold text-blue-700 ring-1 ring-inset ring-blue-200/60">
              {pay}
            </span>
          )}
          {job.experience_level && (
            <span
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-50 px-2.5 py-1 font-semibold capitalize text-emerald-800 ring-1 ring-inset ring-emerald-200/60"
              title={job.experience_level_description || undefined}
            >
              <Icon name="sparkles" size={13} className="text-emerald-600" />
              {job.experience_level}
            </span>
          )}
          {job.remote_eligible && (
            <span className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-50 px-2.5 py-1 font-semibold text-emerald-800 ring-1 ring-inset ring-emerald-200/60">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-600" />
              Remote eligible
            </span>
          )}
          {job.deadline_at && (
            <span className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-2.5 py-1 font-medium text-slate-700">
              <Icon name="clock" size={13} className="text-slate-400" />
              Apply by {formatDate(job.deadline_at)}
            </span>
          )}
        </div>
      </header>

      {/* 2. Eligibility Section */}
      {eligibility && (
        <section aria-label="Eligibility Status">
          {eligibility.eligible ? (
            <div className="flex items-center gap-2.5 rounded-xl border border-emerald-200 bg-emerald-50/50 px-3.5 py-2.5 text-xs text-emerald-900">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-white">
                <Icon name="check" size={12} />
              </span>
              <div className="flex-1">
                <span className="font-semibold">You meet the eligibility criteria</span> for this role based on your profile.
              </div>
            </div>
          ) : (
            <div className="flex items-start gap-2.5 rounded-xl border border-amber-200/80 bg-amber-50/60 p-3.5 text-xs text-amber-900">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-600 text-white">
                <Icon name="alert" size={12} />
              </span>
              <div className="min-w-0 flex-1 space-y-1">
                <p className="font-semibold text-amber-950">Not eligible yet</p>
                {eligibility.reasons.length > 0 && (
                  <ul className="list-disc space-y-0.5 pl-4 leading-normal text-amber-800">
                    {eligibility.reasons.map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
        </section>
      )}

      {/* 3. Why You Match (if available) */}
      {job.match && (
        <section className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
          <div className="flex items-start gap-3.5">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-brand-600 text-base font-extrabold text-white shadow-sm">
              {job.match.score}%
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-bold text-slate-900">Match score breakdown</p>
              <ul className="mt-1 space-y-1 text-xs leading-relaxed text-slate-600">
                {job.match.explanation.map((line) => (
                  <li key={line} className="flex items-start gap-1.5">
                    <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-600" />
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      )}

      {/* 4. Application Action Box */}
      <ApplyBox job={job} />

      {/* 5. About the Role */}
      <section className="space-y-2 border-t border-slate-100 pt-5">
        <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
          About the Role
        </h2>
        <div className="whitespace-pre-line text-sm font-normal leading-relaxed text-slate-700">
          {job.about_job || job.description}
        </div>
      </section>

      {/* 6. Minimum Qualifications */}
      {job.minimum_qualifications && job.minimum_qualifications.length > 0 && (
        <section className="space-y-2 border-t border-slate-100 pt-5">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Minimum Qualifications
          </h2>
          <ul className="space-y-1.5 pl-1 text-sm text-slate-700">
            {job.minimum_qualifications.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-600" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* 7. Preferred Qualifications */}
      {job.preferred_qualifications && job.preferred_qualifications.length > 0 && (
        <section className="space-y-2 border-t border-slate-100 pt-5">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Preferred Qualifications
          </h2>
          <ul className="space-y-1.5 pl-1 text-sm text-slate-700">
            {job.preferred_qualifications.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* 8. Responsibilities */}
      {job.responsibilities && job.responsibilities.length > 0 && (
        <section className="space-y-2 border-t border-slate-100 pt-5">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Responsibilities
          </h2>
          <ul className="space-y-1.5 pl-1 text-sm text-slate-700">
            {job.responsibilities.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-600" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* 9. Perks & Benefits */}
      {job.perks && job.perks.length > 0 && (
        <section className="space-y-2 border-t border-slate-100 pt-5">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Perks & Benefits
          </h2>
          <ul className="space-y-1.5 pl-1 text-sm text-slate-700">
            {job.perks.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* 10. Required & Preferred Skills */}
      {(job.required_skills.length > 0 || job.preferred_skills.length > 0) && (
        <section className="space-y-3 border-t border-slate-100 pt-5">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Required Skills
          </h2>
          {job.required_skills.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {job.required_skills.map((s) => (
                <span
                  key={s}
                  className="inline-flex items-center rounded-md bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-200/60"
                >
                  {s}
                </span>
              ))}
            </div>
          )}
          {job.preferred_skills.length > 0 && (
            <div className="space-y-1.5 pt-1">
              <p className="text-xs font-medium text-slate-500">Nice to have:</p>
              <div className="flex flex-wrap gap-1.5">
                {job.preferred_skills.map((s) => (
                  <Badge key={s} tone="gray">
                    {s}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {/* 11. Additional Information */}
      <section className="space-y-3 border-t border-slate-100 pt-5">
        <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
          Job Overview & Requirements
        </h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-3">
            <span className="block text-[11px] font-medium text-slate-500">Experience</span>
            <span className="mt-0.5 block text-xs font-semibold text-slate-800">
              {experienceLabel(job.experience_min_months, job.experience_max_months)}
            </span>
          </div>

          <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-3">
            <span className="block text-[11px] font-medium text-slate-500">Openings</span>
            <span className="mt-0.5 block text-xs font-semibold text-slate-800">
              {job.openings} {job.openings === 1 ? "position" : "positions"}
            </span>
          </div>

          <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-3">
            <span className="block text-[11px] font-medium text-slate-500">Employment Type</span>
            <span className="mt-0.5 block text-xs font-semibold text-slate-800">
              {EMPLOYMENT_LABELS[job.employment_type]}
            </span>
          </div>

          <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-3">
            <span className="block text-[11px] font-medium text-slate-500">Work Mode</span>
            <span className="mt-0.5 block text-xs font-semibold text-slate-800">
              {LOCATION_TYPE_LABELS[job.location_type]}
            </span>
          </div>

          {job.duration_months != null && (
            <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-3">
              <span className="block text-[11px] font-medium text-slate-500">Duration</span>
              <span className="mt-0.5 block text-xs font-semibold text-slate-800">
                {job.duration_months} month{job.duration_months === 1 ? "" : "s"}
              </span>
            </div>
          )}

          <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-3">
            <span className="block text-[11px] font-medium text-slate-500">Posted Date</span>
            <span className="mt-0.5 block text-xs font-semibold text-slate-800">
              {formatDate(job.published_at || job.created_at)}
            </span>
          </div>
        </div>
      </section>
    </article>
  );
}
