import { useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { TranscriptView } from "@/modules/ai-interview/common/components/TranscriptView";
import { ROUND_LABELS } from "@/modules/ai-interview/common/labels";
import { useEndInterviewMutation, useGetMyInterviewQuery, useGetMyTranscriptQuery } from "@/modules/ai-interview/student/api/studentInterviewsApi";
import { AnswerBox } from "@/modules/ai-interview/student/components/AnswerBox";
import { CodingPanel } from "@/modules/ai-interview/student/components/CodingPanel";
import { ConsentStep } from "@/modules/ai-interview/student/components/ConsentStep";
import { clock, useServerCountdown } from "@/modules/ai-interview/student/hooks/useServerCountdown";
import { Alert, Button, ConfirmDialog, EmptyState, Icon, PageLoader } from "@/shared/ui";

/** The interview: one question at a time, in big type, the answer right under it; the conversation so far below. */
export function InterviewRoomPage() {
  const { interviewId = "" } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();
  const confirm = useConfirmAction();
  const { data: interview, isLoading, isError, refetch } = useGetMyInterviewQuery(interviewId);
  const live = interview?.status === "in_progress";
  const { data: turns = [], refetch: refetchTurns } = useGetMyTranscriptQuery(interviewId, { skip: !live });
  const left = useServerCountdown(interviewId, live);
  const [end] = useEndInterviewMutation();
  const [showAll, setShowAll] = useState(false);

  if (isLoading) return <PageLoader />;
  if (isError || !interview) return <EmptyState icon="alert" title="Interview not found" />;
  if (["completed", "evaluated", "reviewed"].includes(interview.status)) return <Navigate to={`/interviews/mine/${interviewId}/report`} replace />;
  const round = interview.current_round;
  const refresh = () => void Promise.all([refetch(), refetchTurns()]);
  const question = [...turns].reverse().find((t) => t.speaker === "interviewer");
  const coding = round?.type === "coding";

  return (
    <>
      <div className="mb-5 flex flex-wrap items-center gap-3 rounded-2xl bg-white px-4 py-3 shadow-card ring-1 ring-slate-200/60">
        <Link to="/interviews/practice" className="flex h-10 items-center gap-1.5 rounded-xl px-2.5 text-sm font-semibold text-slate-600 ring-1 ring-slate-200 hover:text-navy-950"><Icon name="chevronLeft" size={16} />AI interview</Link>
        <div className="min-w-[180px] flex-1">
          <p className="text-[15px] font-bold text-navy-950">{interview.role}</p>
          <p className="text-xs text-slate-500">{interview.kind === "screening" ? "Company interview" : "Practice"}</p>
        </div>
        {live && round && (
          <div className="flex items-center gap-2 text-[13px] text-slate-600">
            <span>Round {round.number} of {round.total} · {ROUND_LABELS[round.type]}</span>
            <span className="h-1.5 w-28 overflow-hidden rounded-full bg-slate-200"><span className="block h-full bg-brand-600" style={{ width: `${(100 * round.number) / round.total}%` }} /></span>
          </div>
        )}
        {live && left && <span role="timer" className="font-mono text-lg font-extrabold text-navy-950">{clock(left.total)}</span>}
        {live && (
          <Button
            variant="secondary"
            onClick={() =>
              confirm.ask({ title: "End the interview now?", description: "It is scored on what you've answered so far.", confirmLabel: "End interview" }, async () => {
                await end(interviewId).unwrap().then(() => navigate(`/interviews/mine/${interviewId}/report`), notify.apiError);
              })
            }
          >
            End interview
          </Button>
        )}
      </div>

      {interview.status === "invited" && <div className="mx-auto max-w-2xl"><ConsentStep interviewId={interviewId} onStarted={refresh} /></div>}
      {(interview.status === "expired" || interview.status === "cancelled") && <Alert tone="info" title={`This interview was ${interview.status}.`} />}

      {live && (
        <div className={coding ? "grid gap-5 xl:grid-cols-2" : "mx-auto max-w-3xl"}>
          <div className="space-y-4">
            <section aria-live="polite" className="rounded-2xl bg-white p-5 shadow-card ring-1 ring-slate-200/60 sm:p-7">
              <div className="mb-3 flex items-center gap-2">
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-50 text-brand-700 ring-1 ring-brand-200"><Icon name="sparkles" size={16} /></span>
                <span className="text-xs font-bold uppercase tracking-wide text-slate-500">{question?.kind === "follow_up" ? "Follow-up question" : "Question"}</span>
              </div>
              <h1 className="whitespace-pre-wrap text-xl font-bold leading-snug text-navy-950 sm:text-2xl">{question?.text ?? "The interviewer is preparing the first question…"}</h1>
              <p className="mt-3 text-[13px] text-slate-500">Think out loud — how you reason counts, not only the final answer.</p>
            </section>
            <div className="overflow-hidden rounded-2xl bg-white shadow-card ring-1 ring-slate-200/60">
              <AnswerBox interviewId={interviewId} onReply={(pair) => (pair.finished ? navigate(`/interviews/mine/${interviewId}/report`) : refresh())} />
            </div>
            {turns.length > 1 && (
              <section className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200/60">
                <button type="button" aria-expanded={showAll} onClick={() => setShowAll((v) => !v)} className="flex w-full items-center justify-between text-sm font-bold text-navy-950">
                  Conversation so far <Icon name={showAll ? "chevronDown" : "chevronRight"} size={16} />
                </button>
                {showAll && <div className="mt-3 max-h-[50vh] overflow-y-auto"><TranscriptView turns={turns} /></div>}
              </section>
            )}
          </div>
          {coding && round && <CodingPanel interviewId={interviewId} languages={round.languages} onRan={refresh} />}
        </div>
      )}
      <ConfirmDialog {...confirm.dialogProps} />
    </>
  );
}
