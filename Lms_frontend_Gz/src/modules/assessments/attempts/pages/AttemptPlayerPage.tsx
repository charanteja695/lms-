import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { proctoringSessionStorage } from "@/core/lib/storage";
import { useFinishSectionMutation, useSubmitAttemptMutation } from "@/modules/assessments/attempts/api/attemptsApi";
import { ScreenShareBanner } from "@/modules/assessments/attempts/components/player/ScreenShareBanner";
import { IntegrityWarningDialog } from "@/modules/assessments/attempts/components/player/IntegrityWarningDialog";
import { ProctoringIndicator } from "@/modules/assessments/attempts/components/player/ProctoringIndicator";
import { QuestionCard } from "@/modules/assessments/attempts/components/player/QuestionCard";
import { QuestionNavigator } from "@/modules/assessments/attempts/components/player/QuestionNavigator";
import { useAnswerAutosave } from "@/modules/assessments/attempts/hooks/useAnswerAutosave";
import { useAttemptPaper } from "@/modules/assessments/attempts/hooks/useAttemptPaper";
import { formatCountdown, useCountdown } from "@/modules/assessments/attempts/hooks/useCountdown";
import { useExamProctoring } from "@/modules/assessments/attempts/hooks/useExamProctoring";
import { Alert, Button, ConfirmDialog, EmptyState, Icon, PageLoader } from "@/shared/ui";

export function AttemptPlayerPage() {
  const { attemptId = "" } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();
  const confirm = useConfirmAction();
  const { paper, setPaper, isLoading, isError } = useAttemptPaper(attemptId);
  const { save, isSaving } = useAnswerAutosave(attemptId);
  const [finishSection, { isLoading: finishingSection }] = useFinishSectionMutation();
  const [submitAttempt, { isLoading: submitting }] = useSubmitAttemptMutation();
  const [answeredIds, setAnsweredIds] = useState<Set<string>>(() => new Set());

  const { recording, videoRef, screen, flushRecording, warning, resume } = useExamProctoring(attemptId, paper?.attempt.proctoring_level ?? "none", paper?.attempt.status === "in_progress");

  const doSubmit = useCallback(async () => {
    try {
      await flushRecording(); // the recording's last piece is saved with the attempt
      await submitAttempt(attemptId).unwrap();
      navigate(`/attempts/${attemptId}/result`, { replace: true });
    } catch (error) {
      notify.apiError(error);
    }
  }, [attemptId, submitAttempt, navigate, notify, flushRecording]);

  const remainingSeconds = useCountdown(paper?.attempt.remaining_seconds ?? null, () => void doSubmit());

  // A proctored attempt reopened in another tab or browser has no check-in here: the camera checks run again first.
  const testId = paper?.attempt.test_id;
  const needsPrecheck = paper?.attempt.status === "in_progress" && paper.attempt.proctoring_level !== "none" && proctoringSessionStorage.read(attemptId) == null;
  useEffect(() => {
    if (needsPrecheck) navigate(`/proctoring/precheck/${testId}`, { replace: true, state: { attemptId, returnTo: `/attempts/${attemptId}/take` } });
  }, [attemptId, navigate, needsPrecheck, testId]);

  if (isLoading || needsPrecheck) return <PageLoader />;
  if (isError || !paper) {
    return <EmptyState icon="alert" title="Could not load this attempt" action={<Button onClick={() => navigate("/my-tests")}>Back to my tests</Button>} />;
  }

  const { attempt, questions } = paper;
  const currentSection = attempt.sections.find((section) => section.is_current);
  const visibleQuestions = currentSection ? questions.filter((question) => question.section_id === currentSection.section_id) : questions;
  const isLastSection = currentSection ? attempt.sections[attempt.sections.length - 1]?.section_id === currentSection.section_id : true;

  const onSave = (questionId: string, response: Record<string, unknown> | null, flagged?: boolean) => {
    setAnsweredIds((current) => {
      const next = new Set(current);
      if (response && Object.keys(response).length > 0) next.add(questionId);
      else next.delete(questionId);
      return next;
    });
    save(questionId, response, flagged);
  };

  return (
    <>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-5 py-4">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">{attempt.test_title}</h1>
          {currentSection && <p className="text-sm text-slate-500">{currentSection.title}</p>}
        </div>
        {remainingSeconds != null && (
          <span className="flex items-center gap-2 rounded-lg bg-slate-100 px-3 py-2 font-mono text-lg font-semibold text-slate-800">
            <Icon name="clock" size={18} />
            {formatCountdown(remainingSeconds)}
          </span>
        )}
      </div>

      {attempt.status === "paused" && (
        <Alert tone="warning" title="This attempt is paused" className="mb-6">
          Wait for staff to resume it.
        </Alert>
      )}
      {attempt.proctoring_level === "strict" && <ProctoringIndicator videoRef={videoRef} recording={recording} />}
      <ScreenShareBanner screen={screen} />
      <IntegrityWarningDialog warning={warning} onResume={resume} />

      <div className="grid gap-6 lg:grid-cols-[1fr_200px]">
        <div className="space-y-4">
          {visibleQuestions.map((question, index) => (
            <div key={question.question_id} id={`question-${question.question_id}`}>
              <QuestionCard
                attemptId={attemptId}
                question={question}
                index={index}
                onSave={onSave}
                isSaving={isSaving(question.question_id)}
                disabled={attempt.status !== "in_progress"}
              />
            </div>
          ))}

          <div className="flex justify-end gap-3">
            {currentSection && !isLastSection ? (
              <Button
                loading={finishingSection}
                onClick={() =>
                  confirm.ask({ title: "Finish this section?", description: "You cannot come back to it once you move on.", confirmLabel: "Finish section", tone: "primary" }, async () => {
                    try {
                      const nextState = await finishSection(attemptId).unwrap();
                      setPaper({ ...paper, attempt: nextState });
                    } catch (error) {
                      notify.apiError(error);
                    }
                  })
                }
              >
                Finish section
              </Button>
            ) : (
              <Button
                loading={submitting}
                onClick={() => confirm.ask({ title: "Submit this attempt?", description: "You cannot change your answers after this.", confirmLabel: "Submit", tone: "primary" }, doSubmit)}
              >
                Submit
              </Button>
            )}
          </div>
        </div>
        <QuestionNavigator questions={visibleQuestions} answeredIds={answeredIds} />
      </div>
      <ConfirmDialog {...confirm.dialogProps} />
    </>
  );
}
