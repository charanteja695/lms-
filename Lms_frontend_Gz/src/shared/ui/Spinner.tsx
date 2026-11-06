import { cn } from "@/core/lib/cn";

export function Spinner({ size = 20, className }: { size?: number; className?: string }) {
  return (
    <svg className={cn("animate-spin", className)} width={size} height={size} viewBox="0 0 24 24" role="status" aria-label="Loading">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" fill="none" opacity="0.25" />
      <path d="M22 12a10 10 0 00-10-10" stroke="currentColor" strokeWidth="3" fill="none" strokeLinecap="round" />
    </svg>
  );
}

export function PageLoader({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex min-h-[40vh] flex-col items-center justify-center gap-3 text-slate-500">
      <Spinner size={28} className="text-brand-600" />
      <p className="text-sm">{label}</p>
    </div>
  );
}
