import { useInterviewRights } from "@/modules/ai-interview/common/hooks/useInterviewRights";
import { useNavigate, useParams } from "react-router-dom";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { InterviewStatusBadge } from "@/modules/ai-interview/common/components/InterviewBadges";
import {
  useAppealInterviewMutation, useGetMyInterviewQuery, useGetMyReportQuery, useRetakeInterviewMutation, useStartMockMutation,
} from "@/modules/ai-interview/student/api/studentInterviewsApi";
import { RoundFeedback } from "@/modules/ai-interview/student/components/RoundFeedback";
import { Alert, Button, ConfirmDialog, EmptyState, PageHeader, PageLoader } from "@/shared/ui";

const humanize = (key: string) => key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, " ");

/** The candidate's report: overall score, scores by area, round by round with their own words, and what to do next. Never a hire / no-hire. */
export function InterviewReportPage() {
  const { interviewId = "" } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();
  const confirm = useConfirmAction();
  const { data: interview, isLoading } = useGetMyInterviewQuery(interviewId);
  const { data: report } = useGetMyReportQuery(interviewId);
  const [appeal] = useAppealInterviewMutation();
  const { canStart } = useInterviewRights();
  const [retake, { isLoading: retaking }] = useRetakeInterviewMutation();
  const [practise, { isLoading: starting }] = useStartMockMutation();

  if (isLoading) return <PageLoader />;
  if (!interview) return <EmptyState icon="alert" title="Interview not found" />;
  const screening = interview.kind === "screening";
  const max = report?.score_max ?? 5;

  return (
    <>
      <PageHeader
        title={`${interview.role} — report`}
        description={<InterviewStatusBadge status={interview.status} />}
        backTo="/interviews/practice"
        backLabel="AI interview"
        actions={
          <div className="flex flex-wrap gap-2">
            {screening && report?.released && (
              <Button variant="secondary" onClick={() => confirm.ask({ title: "Appeal this result?", description: "A different reviewer looks at it again. You can appeal once.", confirmLabel: "Appeal", tone: "primary", withReason: true }, async (reason) => { await appeal({ id: interviewId, reason: reason || "Please review again." }).unwrap().then(() => notify.success("Appeal sent"), notify.apiError); })}>
                Appeal
              </Button>
            )}
            {interview.retake_granted && canStart && <Button loading={retaking} onClick={() => void retake(interviewId).unwrap().then((next) => navigate(`/interviews/mine/${next.interview_id}`), notify.apiError)}>Retake</Button>}
            {!screening && canStart && <Button icon="refresh" loading={starting} onClick={() => void practise(interview.plan_id).unwrap().then((next) => navigate(`/interviews/mine/${next.interview_id}`), notify.apiError)}>Practise again</Button>}
          </div>
        }
      />
      {!report?.released ? (
        <Alert tone="info" title={screening ? "Your result isn't released yet" : "Your report is being prepared"}>
          {screening ? "The company reviews every interview before you see feedback." : "It appears here as soon as the interview is scored — usually within a minute."}
        </Alert>
      ) : (
        <div className="space-y-5">
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)]">
            <section className="flex flex-col items-center justify-center gap-2 rounded-2xl bg-white p-6 text-center shadow-card ring-1 ring-slate-200/60">
              {report.overall_score != null && (
                <div role="img" aria-label={`Overall ${report.overall_score} out of ${max}`} className="flex h-36 w-36 items-center justify-center rounded-full" style={{ background: `conic-gradient(var(--color-brand-600) ${(report.overall_score / max) * 360}deg, var(--color-slate-200) 0)` }}>
                  <span className="flex h-28 w-28 flex-col items-center justify-center rounded-full bg-white"><strong className="text-4xl font-extrabold text-navy-950">{report.overall_score}</strong><span className="text-xs text-slate-500">out of {max}</span></span>
                </div>
              )}
              {report.summary && <p className="max-w-sm text-[15px] leading-relaxed text-slate-700">{report.summary}</p>}
            </section>
            <section className="space-y-3 rounded-2xl bg-white p-5 shadow-card ring-1 ring-slate-200/60 sm:p-6">
              <h2 className="text-[15px] font-bold text-navy-950">Scores by area</h2>
              {Object.entries(report.criterion_scores).map(([criterion, score]) => (
                <div key={criterion} className="grid grid-cols-[minmax(110px,170px)_minmax(0,1fr)_40px] items-center gap-3">
                  <span className="text-sm font-semibold text-slate-700">{humanize(criterion)}</span>
                  <span className="h-2.5 overflow-hidden rounded-full bg-slate-100"><span className={score < max * 0.6 ? "block h-full bg-accent-500" : "block h-full bg-brand-600"} style={{ width: `${(100 * score) / max}%` }} /></span>
                  <strong className="text-right text-sm text-navy-950">{score}</strong>
                </div>
              ))}
            </section>
          </div>
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
            <section className="space-y-3">
              <h2 className="text-lg font-extrabold text-navy-950">Round by round</h2>
              <RoundFeedback report={report} />
            </section>
            <section className="space-y-4 rounded-2xl bg-white p-5 shadow-card ring-1 ring-slate-200/60">
              {report.strengths.length > 0 && <div><h3 className="text-sm font-bold text-brand-800">What went well</h3><ul className="mt-1 list-disc space-y-1 pl-5 text-[13px] text-slate-700">{report.strengths.map((s) => <li key={s}>{s}</li>)}</ul></div>}
              {report.improvements.length > 0 && <div><h3 className="text-sm font-bold text-accent-700">Work on</h3><ul className="mt-1 list-disc space-y-1 pl-5 text-[13px] text-slate-700">{report.improvements.map((s) => <li key={s}>{s}</li>)}</ul></div>}
              {report.improvement_plan && <div><h3 className="text-sm font-bold text-navy-950">Your plan for next time</h3><p className="mt-1 whitespace-pre-wrap text-[13px] leading-relaxed text-slate-700">{report.improvement_plan}</p></div>}
            </section>
          </div>
        </div>
      )}
      <ConfirmDialog {...confirm.dialogProps} />
    </>
  );
}
