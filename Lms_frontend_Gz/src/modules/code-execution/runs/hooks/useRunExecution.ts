import { useCallback, useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useCreateRunMutation, useLazyGetRunQuery } from "@/modules/code-execution/runs/api/runsApi";
import type { Run, RunCreateBody } from "@/modules/code-execution/runs/types";

const POLL_WAIT_SECONDS = 3;
/** ~2 minutes of polling; the server itself gives up on a stuck job long before this. */
const MAX_POLLS = 40;

/** Submits a run, then long-polls until it's judged. */
export function useRunExecution() {
  const notify = useNotify();
  const [run, setRun] = useState<Run | null>(null);
  const [createRun, { isLoading: isSubmitting }] = useCreateRunMutation();
  const [fetchRun] = useLazyGetRunQuery();
  const [isPolling, setIsPolling] = useState(false);

  const execute = useCallback(
    async (body: RunCreateBody) => {
      setRun(null);
      try {
        const created = await createRun(body).unwrap();
        setRun(created);
        setIsPolling(true);
        let current = created;
        for (let i = 0; i < MAX_POLLS && current.status !== "completed"; i++) {
          current = await fetchRun({ runId: current.run_id, wait: POLL_WAIT_SECONDS }).unwrap();
          setRun(current);
        }
      } catch (error) {
        notify.apiError(error, "Run failed");
      } finally {
        setIsPolling(false);
      }
    },
    [createRun, fetchRun, notify],
  );

  return { run, isExecuting: isSubmitting || isPolling, execute };
}
