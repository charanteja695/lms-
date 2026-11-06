import type { ReactNode } from "react";

import { cn } from "@/core/lib/cn";

const styles = {
  // switches between views of one list, inside a page (SectionTabs is for moving between pages)
  line: {
    list: "flex gap-1 overflow-x-auto border-b border-slate-200",
    tab: "-mb-px border-b-2 px-4 py-2.5",
    on: "border-brand-600 text-brand-700 font-semibold",
    off: "border-transparent text-slate-500 hover:text-slate-800",
  },
  pills: {
    list: "inline-flex max-w-full gap-1 overflow-x-auto rounded-xl bg-slate-100/80 p-1 ring-1 ring-slate-200/60",
    tab: "rounded-lg px-3.5 py-1.5",
    on: "bg-white text-navy-950 shadow-card",
    off: "text-slate-600 hover:text-slate-900",
  },
} as const;

export function Tabs<T extends string>({ tabs, value, onChange, variant = "line" }: {
  tabs: Array<{ value: T; label: ReactNode }>;
  value: T;
  onChange: (value: T) => void;
  variant?: keyof typeof styles;
}) {
  const s = styles[variant];
  return (
    <div role="tablist" className={s.list}>
      {tabs.map((tab) => (
        <button
          key={tab.value}
          role="tab"
          type="button"
          aria-selected={tab.value === value}
          onClick={() => onChange(tab.value)}
          className={cn("whitespace-nowrap text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500", s.tab, tab.value === value ? s.on : s.off)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
