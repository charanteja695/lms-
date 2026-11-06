import type { ApplicationStatus, AssessmentState, Offer, StageEntry } from "@/modules/job-portal/common/types";

export interface MyApplication {
  application_id: string;
  job_id: string;
  job_title: string;
  company_name: string | null;
  status: ApplicationStatus;
  match_score: number | null;
  match_explanation: string[] | null;
  resume_version_no: number;
  assessment: AssessmentState | null;
  offer: Offer | null;
  history: StageEntry[];
  /** The job's steps and how far this application has got (server-computed). */
  progress: { key: string; label: string; state: "done" | "current" | "upcoming" | "stopped" }[];
  /** What the candidate must do now; null while the company is acting. */
  next_action: { kind: "assessment" | "ai_interview" | "offer"; label: string; detail: string; due_at: string | null } | null;
  applied_at: string;
  status_changed_at: string | null;
}
