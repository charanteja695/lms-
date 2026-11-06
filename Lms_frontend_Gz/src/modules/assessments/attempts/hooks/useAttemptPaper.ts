import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useResumeAttemptMutation } from "@/modules/assessments/attempts/api/attemptsApi";
import type { AttemptPaper } from "@/modules/assessments/attempts/paperTypes";

/**
 * The paper (questions + live attempt state) for the player page. A fresh start/prepare hands it
 * over via router state (no extra request); landing here any other way (a refresh, a direct link,
 * or coming back from a crash) calls `resume`, exactly the "after a refresh/crash" case docs/API.md
 * describes.
 */
export function useAttemptPaper(attemptId: string) {
  const location = useLocation();
  const notify = useNotify();
  const [resumeAttempt] = useResumeAttemptMutation();
  const handedOver = (location.state as { paper?: AttemptPaper } | null)?.paper;
  const [paper, setPaper] = useState<AttemptPaper | null>(handedOver ?? null);
  const [isLoading, setIsLoading] = useState(!handedOver);
  const [isError, setIsError] = useState(false);

  useEffect(() => {
    if (handedOver) return;
    let cancelled = false;
    setIsLoading(true);
    resumeAttempt(attemptId)
      .unwrap()
      .then((result) => {
        if (!cancelled) setPaper(result);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setIsError(true);
        notify.apiError(error, "Couldn't resume this attempt");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attemptId]);

  return { paper, setPaper, isLoading, isError };
}
