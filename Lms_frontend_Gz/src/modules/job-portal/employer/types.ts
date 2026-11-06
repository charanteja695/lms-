import type { EmployerStatus, EmploymentType, JobBase, LocationType, JobStatus } from "@/modules/job-portal/common/types";
export type { EmployerStatus, EmploymentType, JobBase, LocationType, JobStatus };

export interface Company {
  organization_id: string;
  company_name: string;
  about: string | null;
  website: string | null;
  industry: string | null;
  company_size: string | null;
  headquarters: string | null;
  status: EmployerStatus;
  review_note: string | null;
  submitted_at: string | null;
  reviewed_at: string | null;
  open_jobs: number;
}

export interface Eligibility {
  graduation_years: { min?: number | null; max?: number | null } | null;
  certificate_course_ids: string[];
  min_scores: { course_id: string; min_percent: number }[];
  institution_ids: string[];
  min_cgpa?: number | null;
  branches?: string[];
  department?: string | null;
  contact_email?: string | null;
  application_url?: string | null;
  salary_period?: "annual" | "monthly" | "hourly" | null;
  is_negotiable?: boolean;
}

export interface Pipeline {
  assessment: { test_id: string; min_percent?: number | null } | null;
  ai_interview: { plan_id: string } | null;
  hr_interview: boolean;
}

export interface EmployerJob extends JobBase {
  eligibility: Partial<Eligibility>;
  institution_ids: string[];
  pipeline: Partial<Pipeline>;
  /** The hiring steps the pipeline makes, in order (server-computed). */
  steps: { key: string; label: string }[];
  review_note: string | null;
  closed_reason: string | null;
  applications: number;
  placed: number;
  created_by: string | null;
}

export interface JobBody {
  employer_org_id?: string;
  stipend_per_month: number | null;
  duration_months: number | null;
  title: string;
  description: string;
  employment_type: EmploymentType;
  location_type: LocationType;
  locations: string[];
  experience_min_months: number;
  experience_max_months: number | null;
  ctc_min: number | null;
  ctc_max: number | null;
  currency: string;
  required_skills: string[];
  preferred_skills: string[];
  openings: number;
  deadline_at: string | null;
  eligibility: Eligibility;
  pipeline: Pipeline;
  banner_text?: string | null;
  banner_type?: 'info' | 'warning' | string | null;
  experience_level?: 'fresher' | 'junior' | 'mid' | 'senior' | 'lead' | string | null;
  experience_level_description?: string | null;
  remote_eligible?: boolean;
  about_job?: string | null;
  responsibilities?: string[];
  minimum_qualifications?: string[];
  preferred_qualifications?: string[];
  perks?: string[];
}

export type JobAction = "submit" | "withdraw-submission" | "pause" | "resume";
