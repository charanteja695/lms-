import type { ReactNode } from "react";

import { cn } from "@/core/lib/cn";
import { useInDrawer } from "@/shared/ui/Drawer";

/** Titled group of fields laid out in a responsive grid (title beside the fields on a wide page, above them in a drawer). */
export function FormSection({ title, description, children, columns = 2, actions }: {
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  columns?: 1 | 2 | 3;
  actions?: ReactNode;
}) {
  const stacked = useInDrawer() !== null;
  return (
    <section className={cn("grid gap-5 border-b border-slate-100 py-7 first:pt-0 last:border-0 last:pb-0", !stacked && "gap-6 lg:grid-cols-3")}>
      <div className={cn(stacked && "flex flex-wrap items-start justify-between gap-3")}>
        <div>
          <h3 className="text-[15px] font-bold text-navy-950">{title}</h3>
          {typeof description !== "string" && description && <div className="mt-1 text-sm text-slate-500">{description}</div>}
        </div>
        {actions && <div className={cn(!stacked && "mt-3")}>{actions}</div>}
      </div>
      <div className={cn("grid gap-4", !stacked && "lg:col-span-2", columns === 2 && "sm:grid-cols-2", columns === 3 && "sm:grid-cols-3")}>{children}</div>
    </section>
  );
}
