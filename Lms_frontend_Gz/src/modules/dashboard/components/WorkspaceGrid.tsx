import { Link } from "react-router-dom";

import { NAV_GROUPS } from "@/app/navigation";
import { useNavItems } from "@/app/useNavItems";
import { cn } from "@/core/lib/cn";
import { Icon } from "@/shared/ui";

// Each section takes one of the logo's colours in turn with a glowing Backlit UI ambient accent.
const TONES = [
  {
    chip: "from-brand-50 to-brand-100 text-brand-700 ring-brand-100",
    bar: "bg-brand-500",
    hover: "hover:border-brand-300",
    glow: "bg-brand-500/15 group-hover:bg-brand-500/25",
  },
  {
    chip: "from-navy-50 to-navy-100 text-navy-800 ring-navy-100",
    bar: "bg-navy-700",
    hover: "hover:border-navy-300",
    glow: "bg-navy-600/15 group-hover:bg-navy-600/25",
  },
  {
    chip: "from-accent-50 to-accent-100 text-accent-700 ring-accent-100",
    bar: "bg-accent-500",
    hover: "hover:border-accent-300",
    glow: "bg-accent-500/15 group-hover:bg-accent-500/25",
  },
] as const;

/** Everything this person can open, with one plain line each, grouped like the sidebar: a starting point for every role. */
export function WorkspaceGrid() {
  const items = useNavItems().filter((i) => i.to !== "/");
  const groups = NAV_GROUPS.filter((g) => g.label && items.some((i) => i.group === g.key));

  return (
    <div className="space-y-8">
      {groups.map((group, index) => {
        const tone = TONES[index % TONES.length] ?? TONES[0];
        const entries = items.filter((i) => i.group === group.key);
        return (
          <section key={group.key} aria-labelledby={`ws-${group.key}`}>
            <h2 id={`ws-${group.key}`} className="mb-3.5 flex items-center gap-2.5 text-sm font-bold uppercase tracking-[0.08em] text-slate-600">
              <span className={cn("h-4 w-1 rounded-full", tone.bar)} aria-hidden="true" />
              {group.label}
            </h2>
            <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {entries.map((item) => (
                <li key={item.to} className="relative group">
                  {/* Kokonut / Backlit UI ambient radiant glow on hover */}
                  <div
                    className={cn(
                      "pointer-events-none absolute -inset-0.5 rounded-3xl blur-md opacity-0 group-hover:opacity-100 transition-opacity duration-300",
                      tone.glow,
                    )}
                    aria-hidden="true"
                  />
                  <Link
                    to={item.to}
                    className={cn(
                      "relative flex h-full items-center gap-4 rounded-2xl border border-slate-200/80 bg-white p-4 sm:p-5 shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lift focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2",
                      tone.hover,
                    )}
                  >
                    <span className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ring-1 transition-transform duration-200 group-hover:scale-105", tone.chip)}>
                      <Icon name={item.icon} size={20} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block font-semibold text-navy-950 transition-colors group-hover:text-brand-700">{item.label}</span>
                    </span>
                    <Icon name="chevronRight" size={18} className="shrink-0 text-slate-300 transition-all duration-200 group-hover:translate-x-1 group-hover:text-brand-600" />
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
