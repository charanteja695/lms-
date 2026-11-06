import { useEffect, useRef, useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useSendProctorHeartbeatMutation } from "@/modules/assessments/attempts/api/proctoringClientApi";

/** Proof of life, every `intervalSeconds` (docs/API.md); surfaces staff directives ("warn") as toasts. */
export function useProctorHeartbeat(sessionId: string | null, intervalSeconds: number) {
  const notify = useNotify();
  const [sendHeartbeat] = useSendProctorHeartbeatMutation();
  const [snapshotIntervalSeconds, setSnapshotIntervalSeconds] = useState(intervalSeconds);
  const seenDirectives = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!sessionId) return;

    const beat = async () => {
      try {
        const result = await sendHeartbeat({ sessionId }).unwrap();
        setSnapshotIntervalSeconds(result.snapshot_interval_seconds);
        for (const directive of result.directives) {
          const key = `${directive.kind}:${directive.created_at}`;
          if (seenDirectives.current.has(key)) continue;
          seenDirectives.current.add(key);
          if (directive.kind === "warn" && directive.message) notify.info("A proctor sent you a message", directive.message);
        }
      } catch {
        /* a missed heartbeat is itself scored server-side (heartbeat_lost); retried on the next tick */
      }
    };

    void beat();
    const timer = window.setInterval(() => void beat(), intervalSeconds * 1000);
    return () => window.clearInterval(timer);
  }, [sessionId, intervalSeconds, sendHeartbeat, notify]);

  return { snapshotIntervalSeconds };
}
