import { useNavigate } from "react-router-dom";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { toApiError } from "@/core/lib/apiError";
import { useJobRights } from "@/modules/job-portal/common/hooks/useJobRights";
import { useCloseJobMutation, useDeleteEmployerJobMutation, useJobActionMutation } from "@/modules/job-portal/employer/api/employerJobsApi";
import type { EmployerJob, JobAction } from "@/modules/job-portal/employer/types";
import { Button, ConfirmDialog } from "@/shared/ui";

/** The actions the job's status allows; the server re-checks each (e.g. EMPLOYER_NOT_VERIFIED on submit). */
export function JobLifecycleActions({ job }: { job: EmployerJob }) {
  const navigate = useNavigate();
  const notify = useNotify();
  const confirm = useConfirmAction();
  const [act, { isLoading }] = useJobActionMutation();
  const [close] = useCloseJobMutation();
  const [deleteJob, { isLoading: isDeleting }] = useDeleteEmployerJobMutation();
  const { isCareersManager } = useJobRights();

  const run = async (action: JobAction, message: string) => {
    try {
      await act({ jobId: job.job_id, action }).unwrap();
      notify.success(message);
    } catch (error) {
      const apiError = toApiError(error);
      notify.error(apiError.message, apiError.details.map((d) => d.message).join(" ") || undefined);
    }
  };

  const handleDelete = () => {
    confirm.ask(
      {
        title: "Delete this job posting?",
        description: "Are you sure you want to permanently delete this job? This action cannot be undone.",
        confirmLabel: "Delete job",
      },
      async () => {
        try {
          await deleteJob(job.job_id).unwrap();
          notify.success("Job deleted successfully");
          navigate("/jobs/employer");
        } catch (error) {
          const apiError = toApiError(error);
          notify.error(apiError.message, apiError.details.map((d) => d.message).join(" ") || undefined);
        }
      }
    );
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      {(job.status === "draft" || job.status === "open" || job.status === "paused") && (
        <Button variant="secondary" icon="edit" onClick={() => navigate(`/jobs/employer/${job.job_id}/edit`)}>Edit</Button>
      )}
      {job.status === "draft" &&
        (isCareersManager ? (
          <Button icon="check" loading={isLoading} onClick={() => void run("submit", "Published: the job is open")}>Publish job</Button>
        ) : (
          <Button icon="check" loading={isLoading} onClick={() => void run("submit", "Submitted for approval")}>Submit for approval</Button>
        ))}
      {job.status === "pending_approval" && <Button variant="secondary" loading={isLoading} onClick={() => void run("withdraw-submission", "Back to draft")}>Withdraw submission</Button>}
      {job.status === "open" && <Button variant="secondary" icon="clock" loading={isLoading} onClick={() => void run("pause", "Job paused")}>Pause</Button>}
      {job.status === "paused" && <Button icon="play" loading={isLoading} onClick={() => void run("resume", "Job reopened")}>Resume</Button>}
      {(job.status === "open" || job.status === "paused") && (
        <Button
          variant="secondary"
          icon="ban"
          className="text-amber-700 hover:text-amber-800"
          onClick={() =>
            confirm.ask({ title: "Close this job?", description: "No more applications. Candidates still in the pipeline can be moved on.", confirmLabel: "Close job", withReason: true }, async (reason) => {
              await close({ jobId: job.job_id, reason: reason || "Closed by the employer" }).unwrap().then(() => notify.success("Job closed"), notify.apiError);
            })
          }
        >
          Close
        </Button>
      )}
      <Button
        variant="danger"
        icon="trash"
        loading={isDeleting}
        onClick={handleDelete}
      >
        Delete
      </Button>
      <ConfirmDialog {...confirm.dialogProps} />
    </div>
  );
}
