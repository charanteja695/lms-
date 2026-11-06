import {
  APPLICATION_STATUS_LABELS, APPLICATION_STATUS_TONES, DRIVE_STATUS_LABELS, DRIVE_STATUS_TONES, EMPLOYER_STATUS_LABELS, EMPLOYER_STATUS_TONES, JOB_STATUS_LABELS, JOB_STATUS_TONES,
} from "@/modules/job-portal/common/labels";
import type { ApplicationStatus, DriveStatus, EmployerStatus, JobStatus } from "@/modules/job-portal/common/types";
import { Badge } from "@/shared/ui";

export const JobStatusBadge = ({ status }: { status: JobStatus }) => <Badge tone={JOB_STATUS_TONES[status]}>{JOB_STATUS_LABELS[status]}</Badge>;
export const EmployerStatusBadge = ({ status }: { status: EmployerStatus }) => <Badge tone={EMPLOYER_STATUS_TONES[status]}>{EMPLOYER_STATUS_LABELS[status]}</Badge>;
export const DriveStatusBadge = ({ status }: { status: DriveStatus }) => <Badge tone={DRIVE_STATUS_TONES[status]}>{DRIVE_STATUS_LABELS[status]}</Badge>;
export const ApplicationStatusBadge = ({ status }: { status: ApplicationStatus }) => (
  <Badge tone={APPLICATION_STATUS_TONES[status] ?? "gray"}>{APPLICATION_STATUS_LABELS[status] ?? status}</Badge>
);

/** The match score job-portal computed (0–100), shown with its colour band. */
export function MatchBadge({ score }: { score: number | null | undefined }) {
  if (score == null) return null;
  return <Badge tone={score >= 75 ? "green" : score >= 50 ? "blue" : "gray"}>{score}% match</Badge>;
}
