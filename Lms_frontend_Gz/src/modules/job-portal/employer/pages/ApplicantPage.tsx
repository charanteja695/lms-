import { useState } from "react";
import { useParams } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { formatDateTime } from "@/core/lib/format";
import { ApplicationStatusBadge, MatchBadge } from "@/modules/job-portal/common/components/JobBadges";
import { StageHistory } from "@/modules/job-portal/common/components/StageHistory";
import { formatCtc } from "@/modules/job-portal/common/format";
import { useGetEmployerJobQuery } from "@/modules/job-portal/employer/api/employerJobsApi";
import { useAddApplicantNoteMutation, useGetApplicantQuery } from "@/modules/job-portal/employer/api/pipelineApi";
import { ApplicantActions } from "@/modules/job-portal/employer/components/applicant/ApplicantActions";
import { ResumeSnapshot } from "@/modules/job-portal/employer/components/applicant/ResumeSnapshot";
import { Button, Card, DescriptionList, EmptyState, PageHeader, PageLoader, Textarea } from "@/shared/ui";

export function ApplicantPage() {
  const { applicationId = "" } = useParams();
  const notify = useNotify();
  const { data: a, isLoading, isError } = useGetApplicantQuery(applicationId, { skip: !applicationId });
  const { data: job } = useGetEmployerJobQuery(a?.job_id ?? "", { skip: !a });
  const [addNote, { isLoading: noting }] = useAddApplicantNoteMutation();
  const [note, setNote] = useState("");

  if (isLoading) return <PageLoader />;
  if (isError || !a) return <EmptyState icon="alert" title="Application not found" />;

  const resumePersonal = (a.resume?.personal as Record<string, unknown>) ?? {};
  const resumeEdu = ((a.resume?.education as Record<string, unknown>[]) ?? [])[0] ?? {};

  const studentName = a.candidate.name || (resumePersonal.name as string) || "Candidate";
  const studentEmail = a.candidate.email || (resumePersonal.email as string) || null;
  const studentPhone = a.candidate.phone || (resumePersonal.phone as string) || null;
  const rollNumber = a.candidate.roll_number || null;
  const institutionName = a.candidate.institution_name || (resumeEdu.institution as string) || null;
  const branchOrCourse = a.candidate.branch || (resumeEdu.field as string) || (resumeEdu.degree as string) || null;
  const gradYear = a.candidate.graduation_year || (resumeEdu.end_year as number | string) || null;
  const cgpaValue = a.candidate.cgpa != null
    ? `${a.candidate.cgpa} / 10`
    : resumeEdu.cgpa != null
      ? `${resumeEdu.cgpa} / 10`
      : null;

  return (
    <>
      <PageHeader
        title={studentName}
        description={
          <span className="flex items-center gap-2">
            <ApplicationStatusBadge status={a.status} />
            <span className="text-slate-600 font-medium">{job?.title || a.job_title}</span>
            {(job?.company_name || a.company_name) && (
              <span className="text-slate-400">· {job?.company_name || a.company_name}</span>
            )}
          </span>
        }
        backTo={`/jobs/employer/${a.job_id}`}
        backLabel="Job Applicants"
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_24rem] mt-2">
        <div className="space-y-4">
          {/* Recruitment Actions */}
          <Card title="Recruitment Actions">
            <ApplicantActions application={a} jobTitle={job?.title ?? a.job_title ?? ""} currency={job?.currency ?? "INR"} />
          </Card>

          {/* Student Profile & Academic Details */}
          <Card title="Candidate & Academic Profile">
            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">Student Information</h4>
                <DescriptionList
                  columns={1}
                  items={[
                    { label: "Full Name", value: studentName },
                    { label: "Email Address", value: studentEmail || <span className="text-slate-400">Not provided</span> },
                    { label: "Phone Number", value: studentPhone || <span className="text-slate-400">Not provided</span> },
                    { label: "Roll / Student ID", value: rollNumber || <span className="text-slate-400">Not available</span> },
                    { label: "Institution", value: institutionName || <span className="text-slate-400">Not specified</span> },
                  ]}
                />
              </div>

              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">Academic & Application Details</h4>
                <DescriptionList
                  columns={1}
                  items={[
                    { label: "Course / Branch", value: branchOrCourse || <span className="text-slate-400">Not specified</span> },
                    { label: "Graduation Year", value: gradYear ? String(gradYear) : <span className="text-slate-400">Not specified</span> },
                    { label: "CGPA", value: cgpaValue || <span className="text-slate-400">Not specified</span> },
                    { label: "Application ID", value: <span className="font-mono text-xs">{a.application_id}</span> },
                    { label: "Applied On", value: formatDateTime(a.applied_at) },
                  ]}
                />
              </div>
            </div>
          </Card>

          {/* Submitted Resume */}
          <Card title={`Submitted Resume (version ${a.resume_version_no}, frozen on apply)`}>
            <ResumeSnapshot resume={a.resume} />
          </Card>

          {/* Cover Note */}
          {a.cover_note && (
            <Card title="Candidate Cover Note">
              <p className="whitespace-pre-wrap text-sm text-slate-800 leading-relaxed bg-slate-50 p-3 rounded-lg border border-slate-200">
                {a.cover_note}
              </p>
            </Card>
          )}
        </div>

        {/* Right Sidebar: Screening, Stages, History, Notes */}
        <div className="space-y-4">
          <Card title="AI Screening & Match" description="Automated screening recommendation.">
            <p className="text-sm font-medium text-slate-900">
              {a.screening.score != null ? `${a.screening.score} / 100 · ${a.screening.recommendation}` : "Not screened yet."}{" "}
              <MatchBadge score={a.match_score} />
            </p>
            {a.screening.reasons.length > 0 && (
              <ul className="mt-2 list-disc pl-5 text-sm text-slate-600 space-y-1">
                {a.screening.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            )}
            {a.screening.red_flags.length > 0 && (
              <ul className="mt-2 list-disc pl-5 text-sm text-red-600 space-y-1 font-medium">
                {a.screening.red_flags.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            )}
          </Card>

          {(a.assessment || a.offer || a.hr_interview_at) && (
            <Card title="Pipeline Milestones">
              <DescriptionList
                columns={1}
                items={[
                  {
                    label: "Assessment",
                    value: a.assessment
                      ? [
                          a.assessment.invite_state,
                          a.assessment.percent != null && `${a.assessment.percent}%`,
                          a.assessment.result,
                          a.assessment.integrity && `integrity: ${a.assessment.integrity}`,
                        ]
                          .filter(Boolean)
                          .join(" · ")
                      : null,
                  },
                  { label: "HR Interview", value: a.hr_interview_at ? formatDateTime(a.hr_interview_at) : null },
                  { label: "Offer", value: a.offer ? `${formatCtc(a.offer.ctc, a.offer.currency)} · ${a.offer.status}` : null },
                ]}
              />
            </Card>
          )}

          <Card title="Application History">
            <StageHistory history={a.history} />
          </Card>

          <Card title="Internal Admin Notes" description="Visible only to authorised recruitment administrators.">
            <ul className="mb-3 space-y-2 text-sm max-h-60 overflow-y-auto">
              {a.notes.length === 0 ? (
                <li className="text-xs text-slate-400 italic">No notes recorded yet.</li>
              ) : (
                a.notes.map((n, i) => (
                  <li key={i} className="rounded bg-slate-50 p-2.5 border border-slate-200">
                    <p className="whitespace-pre-wrap text-slate-800">{n.body}</p>
                    <p className="text-[11px] text-slate-400 mt-1">{formatDateTime(n.created_at)}</p>
                  </li>
                ))
              )}
            </ul>
            <Textarea
              aria-label="New note"
              placeholder="Add an internal note about this applicant…"
              rows={2}
              maxLength={2000}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
            <div className="mt-2 flex justify-end">
              <Button
                size="sm"
                loading={noting}
                disabled={!note.trim()}
                onClick={() =>
                  void addNote({ id: applicationId, body: note.trim() })
                    .unwrap()
                    .then(() => setNote(""), notify.apiError)
                }
              >
                Add Note
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}
