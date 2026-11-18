import type { ReactNode } from "react";

import { cn } from "@/core/lib/cn";

const tones = {
  gray: "bg-slate-100 text-slate-700 ring-slate-200",
  green: "bg-emerald-50 text-[#16A37B] ring-[#16A37B]/20",
  amber: "bg-amber-50 text-amber-800 ring-amber-200",
  orange: "bg-orange-50 text-orange-700 ring-orange-200",
  red: "bg-red-50 text-red-700 ring-red-200",
  blue: "bg-sky-50 text-sky-700 ring-sky-200",
  indigo: "bg-[#F5F4FF] text-[#635BFF] ring-[#635BFF]/20",
  purple: "bg-[#F5F4FF] text-[#635BFF] ring-[#635BFF]/20",
} as const;

export type BadgeTone = keyof typeof tones;

export function Badge({ tone = "gray", children, className }: { tone?: BadgeTone; children: ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset", tones[tone], className)}>
      {children}
    </span>
  );
}
