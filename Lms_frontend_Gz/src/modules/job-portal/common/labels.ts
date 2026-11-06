import type { ApplicationStatus, DriveStatus, EmployerStatus, EmploymentType, JobStatus, LocationType } from "@/modules/job-portal/common/types";
import type { BadgeTone } from "@/shared/ui";

export const EMPLOYMENT_LABELS: Record<EmploymentType, string> = { full_time: "Full-time", part_time: "Part-time", internship: "Internship", contract: "Contract" };
export const LOCATION_TYPE_LABELS: Record<LocationType, string> = { onsite: "On-site", remote: "Remote", hybrid: "Hybrid" };

export const JOB_STATUS_LABELS: Record<JobStatus, string> = { draft: "Draft", pending_approval: "Awaiting approval", open: "Open", paused: "Paused", closed: "Closed" };
export const JOB_STATUS_TONES: Record<JobStatus, BadgeTone> = { draft: "gray", pending_approval: "amber", open: "green", paused: "blue", closed: "gray" };

export const EMPLOYER_STATUS_LABELS: Record<EmployerStatus, string> = { draft: "Draft", pending: "Awaiting verification", verified: "Verified", rejected: "Rejected", suspended: "Suspended" };
export const EMPLOYER_STATUS_TONES: Record<EmployerStatus, BadgeTone> = { draft: "gray", pending: "amber", verified: "green", rejected: "red", suspended: "red" };

export const DRIVE_STATUS_LABELS: Record<DriveStatus, string> = { proposed: "Proposed", accepted: "Accepted", declined: "Declined", completed: "Completed", cancelled: "Cancelled" };
export const DRIVE_STATUS_TONES: Record<DriveStatus, BadgeTone> = { proposed: "amber", accepted: "green", declined: "red", completed: "indigo", cancelled: "gray" };

export const APPLICATION_STATUS_LABELS: Record<ApplicationStatus, string> = {
  applied: "Applied",
  ai_screened: "Screened",
  shortlisted: "Shortlisted",
  rejected: "Not selected",
  assessment_invited: "Assessment invited",
  assessment_completed: "Assessment done",
  ai_interview_invited: "AI interview invited",
  ai_interview_completed: "AI interview done",
  recruiter_review: "Recruiter review",
  hr_interview: "HR interview",
  offered: "Offer made",
  offer_accepted: "Offer accepted",
  offer_declined: "Offer declined",
  placed: "Placed",
  withdrawn: "Withdrawn",
};

export const APPLICATION_STATUS_TONES: Record<ApplicationStatus, BadgeTone> = {
  applied: "gray", ai_screened: "gray", shortlisted: "blue", rejected: "red", assessment_invited: "indigo", assessment_completed: "indigo",
  ai_interview_invited: "indigo", ai_interview_completed: "indigo", recruiter_review: "purple", hr_interview: "purple", offered: "amber",
  offer_accepted: "green", offer_declined: "gray", placed: "green", withdrawn: "gray",
};

export const COMPANY_SIZES = ["1-10", "11-50", "51-200", "201-1000", "1000+"] as const;
