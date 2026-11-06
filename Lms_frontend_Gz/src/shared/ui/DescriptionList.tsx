import type { ReactNode } from "react";

import { cn } from "@/core/lib/cn";

export interface DescriptionItem {
  label: ReactNode;
  value: ReactNode;
  span?: 1 | 2;
}

export function DescriptionList({ items, columns = 2 }: { items: DescriptionItem[]; columns?: 1 | 2 | 3 }) {
  return (
    <dl className={cn("grid gap-x-6 gap-y-4", columns === 1 ? "grid-cols-1" : columns === 2 ? "sm:grid-cols-2" : "sm:grid-cols-2 lg:grid-cols-3")}>
      {items.map((item, index) => (
        <div key={index} className={cn(item.span === 2 && "sm:col-span-2")}>
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{item.label}</dt>
          <dd className="mt-1 break-words text-sm text-slate-900">{item.value ?? <span className="text-slate-400">—</span>}</dd>
        </div>
      ))}
    </dl>
  );
}
