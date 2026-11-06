import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { APPLICATION_STATUS_LABELS } from "@/modules/job-portal/common/labels";
import { TERMINAL_STATUSES } from "@/modules/job-portal/common/terminal";
import type { ApplicationStatus } from "@/modules/job-portal/common/types";
import { useAdvanceApplicantMutation, usePlaceApplicantMutation, useTransitionApplicantMutation } from "@/modules/job-portal/employer/api/pipelineApi";
import { OfferDialog } from "@/modules/job-portal/employer/components/applicant/OfferDialog";
import { RejectDialog } from "@/modules/job-portal/employer/components/job/RejectDialog";
import type { ApplicantDetail } from "@/modules/job-portal/employer/pipelineTypes";
import { Button, Input, Select } from "@/shared/ui";

/** Moves a recruiter may ask for; the pipeline state machine (server) decides which are valid from here (INVALID_TRANSITION). */
const MOVES: ApplicationStatus[] = ["shortlisted", "assessment_invited", "ai_interview_invited", "recruiter_review", "hr_interview"];

export function ApplicantActions({ application, jobTitle, currency }: { application: ApplicantDetail; jobTitle: string; currency: string }) {
  const notify = useNotify();
  const [advance, { isLoading: advancing }] = useAdvanceApplicantMutation();
  const [transition, { isLoading: moving }] = useTransitionApplicantMutation();
  const [place, { isLoading: placing }] = usePlaceApplicantMutation();
  const [to, setTo] = useState<ApplicationStatus | "">("");
  const [interviewAt, setInterviewAt] = useState("");
  const [offering, setOffering] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const id = application.application_id;
  if (TERMINAL_STATUSES.has(application.status)) return null;

  const run = async (work: () => Promise<unknown>, message: string) => {
    try {
      await work();
      notify.success(message);
    } catch (error) {
      notify.apiError(error);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Button loading={advancing} onClick={() => void run(() => advance(id).unwrap(), "Moved to the next stage")}>Next stage</Button>
        <Button variant="secondary" onClick={() => setOffering(true)}>Make offer</Button>
        {application.status === "offer_accepted" && <Button variant="secondary" loading={placing} onClick={() => void run(() => place(id).unwrap(), "Marked as placed")}>Mark placed</Button>}
        <Button variant="danger" onClick={() => setRejecting(true)}>Reject</Button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Select aria-label="Move to" className="w-56" value={to} placeholder="Move to a stage…" options={MOVES.map((m) => ({ value: m, label: APPLICATION_STATUS_LABELS[m] }))} onChange={(e) => setTo(e.target.value as ApplicationStatus)} />
        {to === "hr_interview" && <Input aria-label="Interview time" type="datetime-local" className="w-56" value={interviewAt} onChange={(e) => setInterviewAt(e.target.value)} />}
        <Button variant="secondary" disabled={!to} loading={moving} onClick={() => to && void run(() => transition({ id, to, hr_interview_at: interviewAt ? new Date(interviewAt).toISOString() : undefined }).unwrap(), "Stage changed")}>Move</Button>
      </div>
      {offering && <OfferDialog applicationId={id} defaultTitle={jobTitle} currency={currency} onClose={() => setOffering(false)} />}
      {rejecting && <RejectDialog jobId={application.job_id} ids={[id]} onClose={() => setRejecting(false)} />}
    </div>
  );
}
