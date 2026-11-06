import { useCallback, useEffect, useRef } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { proctoringSessionStorage } from "@/core/lib/storage";
import { useStartAttemptMutation } from "@/modules/assessments/attempts/api/attemptsApi";
import type { AttemptPaper } from "@/modules/assessments/attempts/paperTypes";
import { PROCTORING_LEVEL_LABELS } from "@/modules/assessments/common/labels";
import { Alert, Button, Card, EmptyState, PageHeader } from "@/shared/ui";

export function AttemptInstructionsPage() {
  const { attemptId = "" } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const notify = useNotify();
  const [startAttempt, { isLoading }] = useStartAttemptMutation();
  const { paper, autoStart } = (location.state as { paper?: AttemptPaper; autoStart?: boolean } | null) ?? {};
  const proctored = paper != null && paper.attempt.proctoring_level !== "none";
  const precheckDone = !proctored || proctoringSessionStorage.read(attemptId) != null;

  const start = useCallback(async () => {
    try {
      const started = await startAttempt(attemptId).unwrap();
      navigate(`/attempts/${attemptId}/take`, { replace: true, state: { paper: started } });
    } catch (error) {
      notify.apiError(error);
    }
  }, [attemptId, navigate, notify, startAttempt]);

  // Coming back from a passed proctoring check, its "Start the test" button already was the start.
  const autoStarted = useRef(false);
  useEffect(() => {
    if (!paper || !autoStart || !precheckDone || autoStarted.current) return;
    autoStarted.current = true;
    void start();
  }, [autoStart, paper, precheckDone, start]);

  if (!paper) {
    return <EmptyState icon="alert" title="This page needs to be reached from My tests" action={<Button onClick={() => navigate("/my-tests")}>Go to my tests</Button>} />;
  }

  return (
    <>
      <PageHeader title={paper.attempt.test_title} description="Read the instructions, then start when you're ready. The timer begins the moment you start." />
      <div className="space-y-4">
        {proctored && (
          <Alert tone="warning" title={`${PROCTORING_LEVEL_LABELS[paper.attempt.proctoring_level]} proctoring is enabled`}>
            Stay on this screen for the whole attempt.{" "}
            {precheckDone ? "Your system check is complete." : "Complete the system check below before starting."}
          </Alert>
        )}
        <Card title="Before you start">
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
            <li>{paper.attempt.total_questions} question{paper.attempt.total_questions === 1 ? "" : "s"}.</li>
            {paper.attempt.time_mode === "overall" ? <li>One timer for the whole test.</li> : <li>Each section has its own timer; a finished section cannot be reopened.</li>}
            <li>Answers are saved automatically as you work.</li>
          </ul>
        </Card>
        <div className="flex justify-end">
          {!precheckDone ? (
            <Button
              onClick={() =>
                navigate(`/proctoring/precheck/${paper.attempt.test_id}`, {
                  state: { attemptId, returnTo: `/attempts/${attemptId}/instructions`, returnState: { paper } },
                })
              }
            >
              Complete proctoring check
            </Button>
          ) : (
            <Button loading={isLoading} onClick={() => void start()}>
              Start now
            </Button>
          )}
        </div>
      </div>
    </>
  );
}
