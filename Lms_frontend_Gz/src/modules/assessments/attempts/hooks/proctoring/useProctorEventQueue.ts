import { useCallback, useEffect, useRef } from "react";

import { useReportProctorEventsMutation, type ProctorEventInput } from "@/modules/assessments/attempts/api/proctoringClientApi";

const FLUSH_INTERVAL_MS = 5_000;

/** Batches client-reported proctoring events and flushes them every few seconds (docs/API.md: up to 100 per call). */
export function useProctorEventQueue(sessionId: string | null) {
  const [reportEvents] = useReportProctorEventsMutation();
  const queue = useRef<ProctorEventInput[]>([]);

  const flush = useCallback(() => {
    if (!sessionId || queue.current.length === 0) return;
    const batch = queue.current.splice(0, 100);
    reportEvents({ sessionId, events: batch }).catch(() => {
      /* best-effort: a dropped batch is still independently caught by heartbeats and snapshots */
    });
  }, [sessionId, reportEvents]);

  useEffect(() => {
    if (!sessionId) return;
    const timer = window.setInterval(flush, FLUSH_INTERVAL_MS);
    return () => {
      window.clearInterval(timer);
      flush();
    };
  }, [sessionId, flush]);

  const queueEvent = useCallback((type: string, detail?: Record<string, unknown>) => {
    queue.current.push({ type, occurred_at: new Date().toISOString(), detail });
  }, []);

  return { queueEvent };
}
