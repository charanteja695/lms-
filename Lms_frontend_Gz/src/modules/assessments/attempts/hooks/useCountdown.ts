import { useEffect, useState } from "react";

/**
 * A client-side countdown seeded from the server's `remaining_seconds`/`server_time` (the server
 * is the actual authority: it re-checks the deadline on every save and ends the attempt there —
 * see docs/API.md. This is a display only, recomputed from scratch whenever the server state
 * refreshes (e.g. after resume or finish-section).
 */
export function useCountdown(remainingSeconds: number | null, onExpire?: () => void): number | null {
  const [seconds, setSeconds] = useState(remainingSeconds);

  useEffect(() => {
    setSeconds(remainingSeconds);
  }, [remainingSeconds]);

  useEffect(() => {
    if (seconds == null) return;
    if (seconds <= 0) {
      onExpire?.();
      return;
    }
    const timer = setTimeout(() => setSeconds((current) => (current != null ? current - 1 : current)), 1000);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seconds]);

  return seconds;
}

export function formatCountdown(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const pad = (value: number) => String(value).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}
