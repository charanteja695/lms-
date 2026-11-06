import { useCallback, useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useCreateSubmissionMutation } from "@/modules/code-execution/problems/api/problemsApi";
import { useLazyGetSubmissionQuery } from "@/modules/code-execution/submissions/api/submissionsApi";
import type { Submission } from "@/modules/code-execution/submissions/types";

const POLL_WAIT_SECONDS = 3;
/** ~2 minutes of polling; the server itself gives up on a stuck job long before this. */
const MAX_POLLS = 40;

/** Submits a problem's solution, then long-polls until it's judged. */
export function useSubmissionExecution(problemId: string) {
  const notify = useNotify();
  const [submission, setSubmission] = useState<Submission | null>(null);
  const [createSubmission, { isLoading: isSubmitting }] = useCreateSubmissionMutation();
  const [fetchSubmission] = useLazyGetSubmissionQuery();
  const [isPolling, setIsPolling] = useState(false);

  const submit = useCallback(
    async (language: string, source: string) => {
      setSubmission(null);
      try {
        const created = await createSubmission({ problemId, body: { language, source } }).unwrap();
        setSubmission(created);
        setIsPolling(true);
        let current = created;
        for (let i = 0; i < MAX_POLLS && current.status !== "completed"; i++) {
          current = await fetchSubmission({ submissionId: current.submission_id, wait: POLL_WAIT_SECONDS }).unwrap();
          setSubmission(current);
        }
      } catch (error) {
        notify.apiError(error, "Submission failed");
      } finally {
        setIsPolling(false);
      }
    },
    [createSubmission, fetchSubmission, notify, problemId],
  );

  return { submission, isSubmitting: isSubmitting || isPolling, submit };
}
