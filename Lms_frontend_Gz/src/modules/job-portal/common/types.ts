/** Mirrors job-portal-service's enums (see docs/API.md). */
export type EmploymentType = "full_time" | "part_time" | "internship" | "contract";
export type LocationType = "onsite" | "remote" | "hybrid";
export type JobStatus = "draft" | "pending_approval" | "open" | "paused" | "closed";
export type EmployerStatus = "draft" | "pending" | "verified" | "rejected" | "suspended";
export type DriveStatus = "proposed" | "accepted" | "declined" | "completed" | "cancelled";
export type ApplicationStatus =
  | "applied" | "ai_screened" | "shortlisted" | "rejected" | "assessment_invited" | "assessment_completed" | "ai_interview_invited"
  | "ai_interview_completed" | "recruiter_review" | "hr_interview" | "offered" | "offer_accepted" | "offer_declined" | "placed" | "withdrawn";

/** The posting fields a student and an employer both see. */
export interface JobBase {
  job_id: string;
  employer_id: string;
  company_name: string | null;
  title: string;
  description: string;
  employment_type: EmploymentType;
  location_type: LocationType;
  locations: string[];
  experience_min_months: number;
  experience_max_months: number | null;
  ctc_min: number | null;
  ctc_max: number | null;
  stipend_per_month?: number | null;
  duration_months?: number | null;
  currency: string;
  required_skills: string[];
  preferred_skills: string[];
  openings: number;
  deadline_at: string | null;
  visibility: string;
  drive_id: string | null;
  status: JobStatus;
  published_at: string | null;
  created_at: string;
  banner_text?: string | null;
  banner_type?: 'info' | 'warning' | string | null;
  experience_level?: 'fresher' | 'junior' | 'mid' | 'senior' | 'lead' | string | null;
  experience_level_description?: string | null;
  remote_eligible?: boolean | null;
  about_job?: string | null;
  responsibilities?: string[];
  minimum_qualifications?: string[];
  preferred_qualifications?: string[];
  perks?: string[];
}

export interface StageEntry {
  from_status: ApplicationStatus | null;
  to_status: ApplicationStatus;
  actor: string;
  note: string | null;
  created_at: string;
}

export interface Offer {
  offer_id: string;
  ctc: number;
  currency: string;
  joining_date: string | null;
  role_title: string;
  note: string | null;
  status: string;
  expires_at: string;
  responded_at: string | null;
}

export interface AssessmentState {
  test_id: string | null;
  invite_state: string | null;
  percent: number | null;
  result: string | null;
  integrity: string | null;
}

export interface Drive {
  drive_id: string;
  institution_id: string;
  employer_id: string;
  company_name: string | null;
  institution_name: string | null;
  title: string;
  description: string | null;
  drive_date: string | null;
  status: DriveStatus;
  created_at: string;
}
