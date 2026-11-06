import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { toApiError } from "@/core/lib/apiError";
import { useApplyToJobMutation, useListResumesToApplyQuery } from "@/modules/job-portal/board/api/boardApi";
import type { CandidateJob } from "@/modules/job-portal/board/types";
import { useJobRights } from "@/modules/job-portal/common/hooks/useJobRights";
import { Alert, Button, Icon, Modal, Textarea } from "@/shared/ui";

/**
 * Apply workflow:
 * - Review job details without submitting.
 * - Clicking "Apply now" opens an explicit confirmation dialog.
 * - Application is ONLY submitted when student confirms in the dialog.
 * - Prevents duplicate submissions while request is in flight.
 * - Displays success state and tracking link once backend confirms.
 */
export function ApplyBox({ job }: { job: CandidateJob }) {
  const notify = useNotify();
  const { canApply } = useJobRights();
  const { data: resumes = [], isFetching } = useListResumesToApplyQuery();
  const [apply, { isLoading }] = useApplyToJobMutation();
  const sorted = [...resumes].sort((a, b) => (b.ats_score ?? -1) - (a.ats_score ?? -1));

  const [resumeId, setResumeId] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [reasons, setReasons] = useState<string[]>([]);
  const [sent, setSent] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  // Set default resume when available
  useEffect(() => {
    if (!resumeId && sorted[0]) {
      setResumeId(sorted[0].resume_id);
    }
  }, [resumeId, sorted]);

  // Reset local state when a different job is selected
  useEffect(() => {
    setSent(null);
    setReasons([]);
    setNote(null);
    setConfirmOpen(false);
  }, [job.job_id]);

  const selectedResume = sorted.find((r) => r.resume_id === resumeId) ?? sorted[0];

  // Already applied (either previously in DB or just submitted in this session)
  if (job.applied || sent) {
    return (
      <div
        role="status"
        className="flex flex-wrap items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50/60 p-4"
      >
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-600 text-white shadow-2xs">
          <Icon name="check" size={18} />
        </span>
        <span className="min-w-[180px] flex-1 text-sm text-emerald-950">
          <strong>Application submitted.</strong> Follow each step in My applications.
        </span>
        <Link
          to={`/jobs/applications/${sent ?? job.application_id}`}
          className="inline-flex h-9 items-center rounded-lg border border-emerald-200 bg-white px-3.5 text-xs font-bold text-emerald-800 shadow-2xs transition-colors hover:bg-emerald-50"
        >
          Track application
        </Link>
      </div>
    );
  }

  if (job.status !== "open") {
    return <Alert tone="info">This job isn't taking applications right now.</Alert>;
  }

  if (!canApply) {
    return <Alert tone="info">Applying is turned off for your account.</Alert>;
  }

  if (job.eligibility_result?.eligible === false) {
    return null; // Reasons are shown clearly in the dedicated Eligibility section above
  }

  const handleConfirmApplication = async () => {
    if (isLoading || !resumeId) return;

    try {
      const created = await apply({
        jobId: job.job_id,
        resume_id: resumeId,
        cover_note: note?.trim() || undefined,
      }).unwrap();

      setConfirmOpen(false);
      setSent(created.application_id);
      notify.success("Application submitted successfully.");
    } catch (error) {
      const apiError = toApiError(error);
      if (apiError.code === "NOT_ELIGIBLE") {
        setConfirmOpen(false);
        setReasons(apiError.details.map((d) => d.message));
      } else if (apiError.code === "ALREADY_APPLIED") {
        setConfirmOpen(false);
        notify.info("You have already applied to this job.");
      } else {
        notify.apiError(error, "Could not submit application");
      }
    }
  };

  return (
    <>
      <div className="space-y-3.5 rounded-xl border border-brand-200/80 bg-brand-50/20 p-4">
        {reasons.length > 0 && (
          <Alert tone="warning" title="You're not eligible for this job">
            <ul className="list-disc pl-5">
              {reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </Alert>
        )}

        {!isFetching && resumes.length === 0 ? (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-sm text-slate-700">You need a resume to apply for this job.</span>
            <Link
              to="/career/resumes"
              className="inline-flex h-9 items-center rounded-lg bg-brand-600 px-4 text-xs font-bold text-white shadow-2xs transition-colors hover:bg-brand-700"
            >
              Create a resume
            </Link>
          </div>
        ) : (
          <>
            <div className="space-y-1.5">
              <label
                className="block text-xs font-bold uppercase tracking-wider text-slate-600"
                htmlFor={`resume-${job.job_id}`}
              >
                Select Resume to Submit
              </label>
              <select
                id={`resume-${job.job_id}`}
                value={resumeId}
                onChange={(e) => setResumeId(e.target.value)}
                className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                {sorted.map((r) => (
                  <option key={r.resume_id} value={r.resume_id}>
                    {r.title}
                    {r.ats_score != null ? ` · ATS ${r.ats_score}` : ""}
                  </option>
                ))}
              </select>
            </div>

            {note === null ? (
              <button
                type="button"
                onClick={() => setNote("")}
                className="text-xs font-semibold text-brand-600 hover:text-brand-800 hover:underline"
              >
                + Add a short note (optional)
              </button>
            ) : (
              <div className="space-y-1">
                <label className="block text-xs font-medium text-slate-500" htmlFor={`note-${job.job_id}`}>
                  Short note to the hiring team
                </label>
                <Textarea
                  id={`note-${job.job_id}`}
                  aria-label="Note to the company"
                  rows={3}
                  maxLength={2000}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Briefly highlight why you're a great fit for this role..."
                />
              </div>
            )}

            <div className="flex flex-wrap gap-2.5 pt-1">
              <Button
                size="md"
                className="flex-1 font-semibold"
                disabled={!resumeId || isFetching}
                onClick={() => setConfirmOpen(true)}
              >
                Apply now
              </Button>
              <Link
                to="/interviews/practice"
                className="inline-flex h-10 flex-1 items-center justify-center rounded-xl border border-slate-200 bg-white px-4 text-xs font-semibold text-slate-700 transition-colors hover:bg-slate-50"
              >
                Practise interview first
              </Link>
            </div>
            <p className="text-[11px] text-slate-400">
              The selected resume snapshot is submitted as-is; future edits to your resume won't modify this application.
            </p>
          </>
        )}
      </div>

      {/* Confirmation Dialog */}
      <Modal
        open={confirmOpen}
        onClose={() => {
          if (!isLoading) setConfirmOpen(false);
        }}
        title="Confirm Application"
        description="Please review the details below before submitting your application."
        size="md"
        footer={
          <div className="flex w-full items-center justify-end gap-2.5">
            <Button
              variant="secondary"
              onClick={() => setConfirmOpen(false)}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              loading={isLoading}
              disabled={isLoading || !resumeId}
              onClick={handleConfirmApplication}
            >
              Confirm Application
            </Button>
          </div>
        }
      >
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200/80 bg-slate-50/80 p-4">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Target Role</span>
            <h4 className="mt-0.5 text-base font-bold text-slate-900">{job.title}</h4>
            <p className="mt-0.5 text-sm font-medium text-slate-600">{job.company_name ?? "Company"}</p>
          </div>

          <div className="rounded-xl border border-slate-200/80 bg-slate-50/80 p-4">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Resume to attach</span>
            <p className="mt-1 text-sm font-semibold text-slate-800">
              {selectedResume ? selectedResume.title : "Default Resume"}
              {selectedResume?.ats_score != null ? (
                <span className="ml-2 font-normal text-slate-500">· ATS {selectedResume.ats_score}</span>
              ) : null}
            </p>
          </div>

          {note?.trim() && (
            <div className="rounded-xl border border-slate-200/80 bg-slate-50/80 p-4">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Note to hiring team</span>
              <p className="mt-1 whitespace-pre-line text-xs font-normal text-slate-700 italic">
                "{note.trim()}"
              </p>
            </div>
          )}

          <p className="text-xs leading-relaxed text-slate-500">
            A frozen snapshot of your resume will be shared with the recruiter. Are you sure you want to submit your application?
          </p>
        </div>
      </Modal>
    </>
  );
}
