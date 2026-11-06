import type { JobStatus, JobType } from "@/modules/user-management/downloads/types";
import type { BadgeTone } from "@/shared/ui";

export const JOB_TYPE_LABELS: Record<JobType, string> = {
  user_export: "Users export",
  admin_export: "Admins export",
  institution_export: "Institutions export",
  employer_export: "Employers export",
  user_import: "Users import",
};

export const JOB_STATUS_TONES: Record<JobStatus, BadgeTone> = {
  queued: "gray",
  running: "blue",
  completed: "green",
  failed: "red",
  expired: "amber",
};
