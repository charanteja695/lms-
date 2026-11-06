import { useCallback, useRef, useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useSaveAnswerMutation } from "@/modules/assessments/attempts/api/attemptsApi";

/**
 * Saves one question's answer, debounced, with a client-owned, always-increasing revision per
 * question (the server only compares revisions to each other, never assigns them — see
 * docs/API.md "revision is the client's change counter"). Starting from the current time in seconds
 * rather than 1 means a resumed session's counter never falls below an earlier session's. Seconds, not
 * milliseconds: the server caps a revision at 2,000,000,000 (the time in seconds passes that in 2033).
 */
export function useAnswerAutosave(attemptId: string) {
  const notify = useNotify();
  const [saveAnswer] = useSaveAnswerMutation();
  const revisions = useRef<Record<string, number>>({});
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const [savingIds, setSavingIds] = useState<Set<string>>(new Set());

  const save = useCallback(
    (questionId: string, response: Record<string, unknown> | null, flagged?: boolean) => {
      clearTimeout(timers.current[questionId]);
      timers.current[questionId] = setTimeout(async () => {
        const revision = (revisions.current[questionId] ?? Math.floor(Date.now() / 1000)) + 1;
        revisions.current[questionId] = revision;
        setSavingIds((current) => new Set(current).add(questionId));
        try {
          const saved = await saveAnswer({ attemptId, questionId, response, revision, flagged }).unwrap();
          if (saved.status === "rejected") notify.error("That answer wasn't saved", "Check it and try again.");
        } catch (error) {
          notify.apiError(error, "Couldn't save that answer");
        } finally {
          setSavingIds((current) => {
            const next = new Set(current);
            next.delete(questionId);
            return next;
          });
        }
      }, 600);
    },
    [attemptId, saveAnswer, notify],
  );

  return { save, isSaving: (questionId: string) => savingIds.has(questionId) };
}
