import { cn } from "@/core/lib/cn";

/** A 0–100 score as a ring. Green at 80+, amber at 60+, orange below: the bands only colour it, the number is the server's. */
export function ScoreRing({ score, size = 64, label = "ATS score", className }: { score: number; size?: number; label?: string; className?: string }) {
  const tone = score >= 80 ? "var(--color-brand-600)" : score >= 60 ? "#f59e0b" : "var(--color-accent-600)";
  const inner = Math.round(size * 0.78);
  return (
    <div
      role="img"
      aria-label={`${label} ${score} out of 100`}
      className={cn("flex shrink-0 items-center justify-center rounded-full", className)}
      style={{ width: size, height: size, background: `conic-gradient(${tone} ${score * 3.6}deg, var(--color-slate-200) 0)` }}
    >
      <span className="flex items-center justify-center rounded-full bg-white font-extrabold text-navy-950" style={{ width: inner, height: inner, fontSize: Math.max(12, size * 0.28) }}>
        {score}
      </span>
    </div>
  );
}
