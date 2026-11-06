import { useNavigate } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { usePrepareAttemptMutation } from "@/modules/assessments/attempts/api/attemptsApi";

/** Opens a test for the learner: a new attempt goes to its instructions (camera checks first for a proctored one). */
export function useStartTest() {
  const navigate = useNavigate();
  const notify = useNotify();
  const [prepare, { isLoading }] = usePrepareAttemptMutation();

  const start = async (testId: string) => {
    try {
      const paper = await prepare({ testId, startNow: false }).unwrap();
      // an attempt already open comes back without its questions: the player fetches them by resuming
      if (paper.attempt.status === "not_started") navigate(`/attempts/${paper.attempt.attempt_id}/instructions`, { state: { paper } });
      else navigate(`/attempts/${paper.attempt.attempt_id}/take`);
    } catch (error) {
      notify.apiError(error, "Could not open the test");
    }
  };
  return { start, starting: isLoading };
}
