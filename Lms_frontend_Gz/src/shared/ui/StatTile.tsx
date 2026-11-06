import { Link } from "react-router-dom";

import { cn } from "@/core/lib/cn";
import { Icon, type IconName } from "./Icon";
import { AnimatedCounter } from "./AnimatedCounter";

export function StatTile({ icon, label, value, to }: { icon: IconName; label: string; value: number | string; to?: string }) {
  const isNumber = typeof value === "number";

  const body = (
    <div
      className={cn(
        "group relative flex flex-col items-start gap-3 overflow-hidden rounded-2xl border border-slate-200/80 bg-white p-4 shadow-card sm:flex-row sm:items-center sm:gap-4 sm:p-5 transition-all duration-200",
        to && "hover:-translate-y-1 hover:border-brand-300 hover:shadow-lift cursor-pointer",
      )}
    >
      {/* Subtle Backlit Ambient Accent */}
      <div
        className="pointer-events-none absolute -right-6 -top-6 h-20 w-20 rounded-full bg-brand-500/5 blur-xl transition-all duration-300 group-hover:scale-150 group-hover:bg-brand-500/10"
        aria-hidden="true"
      />

      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl sm:h-12 sm:w-12 bg-gradient-to-br from-brand-50 to-brand-100 text-brand-700 ring-1 ring-brand-100 transition-transform duration-200 group-hover:scale-105">
        <Icon name={icon} size={22} />
      </div>

      <div className="min-w-0">
        <p className="text-sm font-medium text-slate-500">{label}</p>
        <p className="text-[26px] font-bold leading-tight tabular-nums text-navy-950">
          {isNumber ? <AnimatedCounter value={value} /> : value}
        </p>
      </div>

      {to && (
        <Icon
          name="chevronRight"
          size={18}
          className="absolute right-4 top-4 text-slate-300 transition-all duration-200 group-hover:translate-x-0.5 group-hover:text-brand-600 sm:static sm:ml-auto"
        />
      )}
    </div>
  );

  return to ? (
    <Link
      to={to}
      className="rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 block"
    >
      {body}
    </Link>
  ) : (
    body
  );
}
