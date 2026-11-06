import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { cn } from "@/core/lib/cn";
import { Icon, type IconName } from "@/shared/ui";

const TONES = {
  navy: "bg-navy-950 text-white",
  brand: "bg-brand-600 text-white",
  soft: "bg-brand-50 text-brand-700 ring-1 ring-brand-100",
  accent: "bg-accent-50 text-accent-700 ring-1 ring-accent-100",
} as const;

/** One box in the organisation tree: a role chip, a name, a line of detail, and its children below a guide line. */
export function TreeNode({ icon, tone, role, title, detail, to, extra, children }: {
  icon: IconName;
  tone: keyof typeof TONES;
  role: string;
  title: string;
  detail?: ReactNode;
  to?: string;
  extra?: ReactNode;
  children?: ReactNode;
}) {
  const box = (
    <div className={cn("flex items-center gap-3 rounded-2xl border border-slate-200/80 bg-white px-4 py-3 shadow-card", to && "transition-colors hover:border-brand-300 hover:shadow-lift")}>
      <span className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-xl", TONES[tone])}>
        <Icon name={icon} size={18} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400">{role}</span>
        <span className="block font-bold text-navy-950 sm:truncate">{title}</span>
        {detail && <span className="block truncate text-xs text-slate-500">{detail}</span>}
      </span>
      {extra}
      {to && <Icon name="chevronRight" size={16} className="shrink-0 text-slate-400" />}
    </div>
  );
  return (
    <li className="relative">
      {to ? <Link to={to} className="block rounded-2xl">{box}</Link> : box}
      {children && <ul className="ml-3 mt-3 space-y-3 border-l-2 border-dashed border-slate-200 pl-3 sm:ml-8 sm:pl-8">{children}</ul>}
    </li>
  );
}

/** A small count chip: "12 staff". */
export function Count({ value, label }: { value: number; label: string }) {
  return (
    <span className="inline-flex shrink-0 items-baseline gap-1 rounded-lg bg-slate-50 px-2 py-1 text-xs text-slate-500 ring-1 ring-slate-200">
      <span className="font-bold tabular-nums text-navy-950">{value.toLocaleString()}</span>
      {label}
    </span>
  );
}
