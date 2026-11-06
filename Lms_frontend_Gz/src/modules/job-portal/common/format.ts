import { EMPLOYMENT_LABELS, LOCATION_TYPE_LABELS } from "@/modules/job-portal/common/labels";
import type { JobBase } from "@/modules/job-portal/common/types";

/** CTC is a yearly amount in the job's currency; INR reads in lakhs, others in thousands. */
export function formatCtc(amount: number | null | undefined, currency = "INR"): string | null {
  if (amount == null) return null;
  if (currency === "INR") return `₹${+(amount / 100_000).toFixed(1)} L`;
  return `${currency} ${Math.round(amount / 1000)}k`;
}

export function ctcRange(job: Pick<JobBase, "ctc_min" | "ctc_max" | "currency">): string | null {
  const low = formatCtc(job.ctc_min, job.currency);
  const high = formatCtc(job.ctc_max, job.currency);
  if (low && high) return low === high ? low : `${low} – ${high}`;
  return low ?? high;
}

/** Internships: "₹25,000/month · 6 months" (either part may be missing). */
export function stipendLabel(job: Pick<JobBase, "stipend_per_month" | "duration_months" | "currency">): string | null {
  const pay = job.stipend_per_month != null ? `${job.currency === "INR" ? "₹" : `${job.currency} `}${job.stipend_per_month.toLocaleString("en-IN")}/month` : null;
  const length = job.duration_months != null ? `${job.duration_months} month${job.duration_months === 1 ? "" : "s"}` : null;
  return [pay, length].filter(Boolean).join(" · ") || null;
}

export function experienceLabel(min: number, max: number | null): string {
  const years = (months: number) => (months % 12 === 0 ? `${months / 12}` : (months / 12).toFixed(1));
  if (min === 0 && (max == null || max === 0)) return "Freshers";
  return max == null ? `${years(min)}+ yrs` : `${years(min)}–${years(max)} yrs`;
}

export function jobMeta(job: JobBase): string {
  const where = job.location_type === "remote" ? LOCATION_TYPE_LABELS.remote : [LOCATION_TYPE_LABELS[job.location_type], job.locations.join(", ")].filter(Boolean).join(" · ");
  return [EMPLOYMENT_LABELS[job.employment_type], where, experienceLabel(job.experience_min_months, job.experience_max_months), job.employment_type === "internship" ? stipendLabel(job) : ctcRange(job)].filter(Boolean).join(" · ");
}
