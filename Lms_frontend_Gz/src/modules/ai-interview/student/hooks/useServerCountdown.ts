import { useEffect, useState } from "react";

import { useGetTimeLeftQuery } from "@/modules/ai-interview/student/api/studentInterviewsApi";

/** Seconds left by the server's clock: re-read every 30 s and counted down locally in between (a display only). */
export function useServerCountdown(interviewId: string, active: boolean) {
  const { data } = useGetTimeLeftQuery(interviewId, { skip: !active, pollingInterval: active ? 30_000 : 0 });
  const [left, setLeft] = useState<{ round: number; total: number } | null>(null);

  useEffect(() => {
    if (data) setLeft({ round: data.round_seconds_left, total: data.interview_seconds_left });
  }, [data]);

  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setLeft((l) => (l ? { round: Math.max(0, l.round - 1), total: Math.max(0, l.total - 1) } : l)), 1000);
    return () => window.clearInterval(timer);
  }, [active]);

  return left;
}

export const clock = (seconds: number) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
