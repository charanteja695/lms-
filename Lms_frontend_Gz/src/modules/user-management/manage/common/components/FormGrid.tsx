import type { ReactNode } from "react";

/** Fields in two columns (one on phones), with an optional small heading. Fields can span both with `sm:col-span-2`. */
export function FormGrid({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <div className="space-y-3">
      {title && <h3 className="text-xs font-bold uppercase tracking-[0.08em] text-slate-500">{title}</h3>}
      <div className="grid gap-4 sm:grid-cols-2">{children}</div>
    </div>
  );
}
