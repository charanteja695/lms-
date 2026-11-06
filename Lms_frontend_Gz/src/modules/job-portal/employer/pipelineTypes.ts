import type { ApplicationStatus, AssessmentState, Offer, StageEntry } from "@/modules/job-portal/common/types";

export interface Candidate {
  user_id: string;
  name: string;
  email: string | null;
  phone?: string | null;
  roll_number?: string | null;
  institution_name?: string | null;
  branch?: string | null;
  graduation_year?: number | null;
  cgpa?: number | null;
}

export interface Screening {
  score: number | null;
  recommendation: string | null;
  source: string | null;
  reasons: string[];
  red_flags: string[];
}

export interface Applicant {
  application_id: string;
  job_id: string;
  job_title?: string | null;
  company_name?: string | null;
  candidate: Candidate;
  status: ApplicationStatus;
  match_score: number | null;
  match_explanation: string[] | null;
  screening: Screening;
  assessment: AssessmentState | null;
  interview: Record<string, unknown> | null;
  hr_interview_at: string | null;
  cover_note: string | null;
  resume_version_no: number;
  applied_at: string;
  status_changed_at: string | null;
  decision_reason: string | null;
}

export interface ApplicantDetail extends Applicant {
  resume: Record<string, unknown>;
  history: StageEntry[];
  notes: { body: string; author_user_id?: string; created_at: string }[];
  offer: Offer | null;
}

export interface Ranking {
  shortlist_at: number;
  reject_below: number;
  shortlist: Applicant[];
  review: Applicant[];
  reject: Applicant[];
  unscreened: Applicant[];
  note: string;
}

export interface Funnel {
  job_id: string;
  by_status: Record<string, number>;
  /** This job's working tabs; filter the applicants list by a tab's `statuses`. */
  stages: { key: string; label: string; statuses: ApplicationStatus[]; count: number }[];
  total: number;
  placed: number;
  openings: number;
}

export interface ScreeningDecision {
  application_id: string | null;
  kind: string;
  source: string;
  model: string | null;
  prompt_key: string | null;
  prompt_version: number | null;
  input_digest: string;
  score: number | null;
  recommendation: string;
  output: Record<string, unknown>;
  created_at: string;
}
