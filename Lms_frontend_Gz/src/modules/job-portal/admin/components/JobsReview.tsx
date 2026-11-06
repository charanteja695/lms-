import { useState } from "react";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { formatDate } from "@/core/lib/format";
import { JobStatusBadge } from "@/modules/job-portal/common/components/JobBadges";
import { jobMeta } from "@/modules/job-portal/common/format";
import { useListJobsForReviewQuery, useReviewJobMutation } from "@/modules/job-portal/admin/api/jobAdminApi";
import type { EmployerJob } from "@/modules/job-portal/employer/types";
import { Badge, Button, Card, ConfirmDialog, EmptyState, Spinner } from "@/shared/ui";

/** Jobs awaiting approval, oldest first; approving opens the job and starts matching it to students. */
export function JobsReview() {
  const notify = useNotify();
  const confirm = useConfirmAction();
  const { data, isFetching } = useListJobsForReviewQuery({ status: "pending_approval", per_page: 50 });
  const [review] = useReviewJobMutation();
  const [open, setOpen] = useState<string | null>(null);
  const jobs = data?.items ?? [];

  if (isFetching && jobs.length === 0) return <Spinner />;
  if (jobs.length === 0) return <EmptyState icon="check" title="No jobs waiting for approval" description="New jobs from companies appear here for review." />;

  return (
    <div className="space-y-3">
      {jobs.map((job: EmployerJob) => (
        <Card key={job.job_id} title={job.title} description={`${job.company_name ?? "Company"} · ${jobMeta(job)}`} actions={<JobStatusBadge status={job.status} />}>
          <div className="flex flex-wrap gap-1">{job.required_skills.map((s) => <Badge key={s}>{s}</Badge>)}</div>
          {open === job.job_id && <p className="mt-3 whitespace-pre-wrap text-sm text-slate-700">{job.description}</p>}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button size="sm" variant="ghost" onClick={() => setOpen(open === job.job_id ? null : job.job_id)}>{open === job.job_id ? "Hide description" : "Read description"}</Button>
            <span className="flex-1 text-xs text-slate-400">Deadline {formatDate(job.deadline_at)}</span>
            <Button size="sm" variant="secondary" onClick={() => confirm.ask({ title: "Send back?", description: "The note is shown to the company; the job returns to draft.", confirmLabel: "Send back", withReason: true }, async (note) => { await review({ id: job.job_id, approve: false, note: note || "Please revise" }).unwrap().then(() => notify.success("Sent back"), notify.apiError); })}>Send back</Button>
            <Button size="sm" onClick={() => void review({ id: job.job_id, approve: true }).unwrap().then(() => notify.success("Job approved and live"), notify.apiError)}>Approve</Button>
          </div>
        </Card>
      ))}
      <ConfirmDialog {...confirm.dialogProps} />
    </div>
  );
}
