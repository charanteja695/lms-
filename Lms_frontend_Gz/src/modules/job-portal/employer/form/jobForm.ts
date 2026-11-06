import type { EmployerJob, EmploymentType, JobBody, LocationType } from "@/modules/job-portal/employer/types";

export type Picked = { id: string; label: string };

export interface CourseOption {
  id: string;
  label: string;
}

export interface ScoreRequirement {
  id: string;
  label: string;
  min_percent: string;
}

export interface JobFormValues {
  // Hiring company
  company: { id: string; label: string } | null;

  // Basic Information
  title: string;
  description: string;
  employment_type: EmploymentType;
  location_type: LocationType;
  locations: string; // comma-separated in the form
  department: string;
  experience_min_years: string;
  experience_max_years: string;

  // Job Description
  banner_text: string;
  banner_type: "info" | "warning";
  experience_level: "fresher" | "junior" | "mid" | "senior" | "lead";
  experience_level_description: string;
  remote_eligible: boolean;
  about_job: string;
  minimum_qualifications: string[];
  preferred_qualifications: string[];
  responsibilities: string[];
  perks: string[];

  // Salary & Compensation
  ctc_min_lakhs: string;
  ctc_max_lakhs: string;
  salary_period: "annual" | "monthly" | "hourly";
  is_negotiable: boolean;
  stipend_per_month: string;
  duration_months: string;
  currency: string;
  required_skills: string; // comma-separated in the form
  preferred_skills: string; // comma-separated in the form
  openings: string;

  // Application Details
  deadline: string; // YYYY-MM-DD
  application_type: "internal" | "external";
  application_url: string;
  contact_email: string;

  // Eligibility Criteria
  graduation_min: string;
  graduation_max: string;
  min_cgpa: string;
  branches: string; // comma-separated
  certificate_courses: CourseOption[];
  min_scores: ScoreRequirement[];
  institutions: { id: string; label: string }[];

  // Pipeline
  assessment: { id: string; label: string } | null;
  assessment_min_percent: string;
  ai_interview: { id: string; label: string } | null;
  hr_interview: boolean;
}

export function emptyJobForm(): JobFormValues {
  return {
  company: null,
  title: "",
  description: "",
  employment_type: "full_time",
  location_type: "onsite",
  locations: "",
  department: "",
  experience_min_years: "0",
  experience_max_years: "",

  banner_text: "",
  banner_type: "info",
  experience_level: "fresher",
  experience_level_description: "",
  remote_eligible: false,
  about_job: "",
  minimum_qualifications: [],
  preferred_qualifications: [],
  responsibilities: [],
  perks: [],

  ctc_min_lakhs: "",
  ctc_max_lakhs: "",
  salary_period: "annual",
  is_negotiable: false,
  stipend_per_month: "",
  duration_months: "",
  currency: "INR",
  required_skills: "",
  preferred_skills: "",
  openings: "1",
  deadline: "",
  application_type: "internal",
  application_url: "",
  contact_email: "",
  graduation_min: "",
  graduation_max: "",
  min_cgpa: "",
  branches: "",
  certificate_courses: [],
  min_scores: [],
  institutions: [],
  assessment: null,
  assessment_min_percent: "",
  ai_interview: null,
  hr_interview: false,
  };
}

const list = (s: string) =>
  s
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);

const num = (s: string) => (s.trim() === "" ? null : Number(s));
const months = (years: string) => (years.trim() === "" ? null : Math.round(Number(years) * 12));
const amount = (lakhs: string, currency: string) => (lakhs.trim() === "" ? null : Math.round(Number(lakhs) * (currency === "INR" ? 100_000 : 1000)));
const fromAmount = (value: number | null, currency: string) => (value == null ? "" : String(value / (currency === "INR" ? 100_000 : 1000)));

/** The job stores ids only: course labels are left empty and resolved for display (CourseTitleCell); others show the id. */
export function jobToForm(job: EmployerJob): JobFormValues {
  const e = (job.eligibility as Record<string, any>) || {};
  const p = (job.pipeline as Record<string, any>) || {};
  return {
    company: { id: job.employer_id, label: job.company_name ?? "" },
    stipend_per_month: job.stipend_per_month == null ? "" : String(job.stipend_per_month),
    duration_months: job.duration_months == null ? "" : String(job.duration_months),
    title: job.title || "",
    description: job.description || "",
    employment_type: job.employment_type || "full_time",
    location_type: job.location_type || "onsite",
    locations: Array.isArray(job.locations) ? job.locations.join(", ") : "",
    department: (e.department as string) ?? "",
    experience_min_years: job.experience_min_months != null ? String(job.experience_min_months / 12) : "0",
    experience_max_years: job.experience_max_months == null ? "" : String(job.experience_max_months / 12),
    ctc_min_lakhs: fromAmount(job.ctc_min, job.currency),
    ctc_max_lakhs: fromAmount(job.ctc_max, job.currency),
    salary_period: (e.salary_period as any) ?? "annual",
    is_negotiable: Boolean(e.is_negotiable),
    currency: job.currency || "INR",
    required_skills: Array.isArray(job.required_skills) ? job.required_skills.join(", ") : "",
    preferred_skills: Array.isArray(job.preferred_skills) ? job.preferred_skills.join(", ") : "",
    openings: String(job.openings ?? 1),
    deadline: job.deadline_at?.slice(0, 10) ?? "",
    graduation_min: e.graduation_years?.min != null ? String(e.graduation_years.min) : "",
    graduation_max: e.graduation_years?.max != null ? String(e.graduation_years.max) : "",
    min_cgpa: e.min_cgpa != null ? String(e.min_cgpa) : "",
    branches: Array.isArray(e.branches) ? e.branches.join(", ") : "",
    certificate_courses: (e.certificate_course_ids ?? []).map((id: string) => ({ id, label: "" })),
    min_scores: (e.min_scores ?? []).map((s: any) => ({ id: s.course_id, label: "", min_percent: String(s.min_percent) })),
    institutions: (job.institution_ids ?? []).map((id) => ({ id, label: `Institution #${id}` })),
    application_type: e.application_url ? "external" : "internal",
    application_url: (e.application_url as string) ?? "",
    contact_email: (e.contact_email as string) ?? "",
    assessment: p.assessment ? { id: p.assessment.test_id, label: `Test #${p.assessment.test_id}` } : null,
    assessment_min_percent: p.assessment?.min_percent != null ? String(p.assessment.min_percent) : "",
    ai_interview: p.ai_interview ? { id: p.ai_interview.plan_id, label: `Plan #${p.ai_interview.plan_id}` } : null,
    hr_interview: p.hr_interview ?? false,

    banner_text: job.banner_text ?? "",
    banner_type: (job.banner_type as any) ?? "info",
    experience_level: (job.experience_level as any) ?? "fresher",
    experience_level_description: job.experience_level_description ?? "",
    remote_eligible: Boolean(job.remote_eligible),
    about_job: job.about_job ?? job.description ?? "",
    minimum_qualifications: Array.isArray(job.minimum_qualifications) ? job.minimum_qualifications : [],
    preferred_qualifications: Array.isArray(job.preferred_qualifications) ? job.preferred_qualifications : [],
    responsibilities: Array.isArray(job.responsibilities) ? job.responsibilities : [],
    perks: Array.isArray(job.perks) ? job.perks : [],
  };
}

export function toJobBody(v: JobFormValues): JobBody {
  return {
    title: (v.title || "").trim(),
    description: (v.about_job || "").trim() || (v.description || "").trim() || (v.title || "").trim() || "Job opening details",
    employment_type: v.employment_type || "full_time",
    location_type: v.location_type || "onsite",
    locations: list(v.locations || ""),
    experience_min_months: months(v.experience_min_years || "0") ?? 0,
    experience_max_months: months(v.experience_max_years || ""),
    ctc_min: v.employment_type === "internship" ? null : amount(v.ctc_min_lakhs || "", v.currency || "INR"),
    ctc_max: v.employment_type === "internship" ? null : amount(v.ctc_max_lakhs || "", v.currency || "INR"),
    stipend_per_month: v.employment_type === "internship" ? num(v.stipend_per_month || "") : null,
    duration_months: v.employment_type === "internship" ? num(v.duration_months || "") : null,
    currency: v.currency || "INR",
    required_skills: list(v.required_skills || ""),
    preferred_skills: list(v.preferred_skills || ""),
    openings: Number(v.openings) || 1,
    deadline_at: v.deadline ? `${v.deadline}T23:59:59Z` : null,
    eligibility: {
      graduation_years: (v.graduation_min || v.graduation_max) ? { min: num(v.graduation_min || ""), max: num(v.graduation_max || "") } : null,
      certificate_course_ids: (v.certificate_courses || []).map((c) => c.id),
      min_scores: (v.min_scores || []).map((s) => ({ course_id: s.id, min_percent: Number(s.min_percent) || 0 })),
      institution_ids: (v.institutions || []).map((i) => i.id),
      min_cgpa: (v.min_cgpa || "").trim() ? Number(v.min_cgpa) : null,
      branches: list(v.branches || ""),
      department: (v.department || "").trim() || null,
      contact_email: (v.contact_email || "").trim() || null,
      application_url: v.application_type === "external" && (v.application_url || "").trim() ? (v.application_url || "").trim() : null,
      salary_period: v.salary_period || "annual",
      is_negotiable: Boolean(v.is_negotiable),
    },
    pipeline: {
      assessment: v.assessment ? { test_id: v.assessment.id, min_percent: num(v.assessment_min_percent || "") } : null,
      ai_interview: v.ai_interview ? { plan_id: v.ai_interview.id } : null,
      hr_interview: Boolean(v.hr_interview),
    },
    banner_text: (v.banner_text || "").trim() || null,
    banner_type: v.banner_type || "info",
    experience_level: v.experience_level || "fresher",
    experience_level_description: (v.experience_level_description || "").trim() || null,
    remote_eligible: Boolean(v.remote_eligible),
    minimum_qualifications: (v.minimum_qualifications || []).map((s) => (s || "").trim()).filter(Boolean),
    preferred_qualifications: (v.preferred_qualifications || []).map((s) => (s || "").trim()).filter(Boolean),
    about_job: (v.about_job || "").trim() || (v.description || "").trim(),
    responsibilities: (v.responsibilities || []).map((s) => (s || "").trim()).filter(Boolean),
    perks: (v.perks || []).map((s) => (s || "").trim()).filter(Boolean),
  };
}
