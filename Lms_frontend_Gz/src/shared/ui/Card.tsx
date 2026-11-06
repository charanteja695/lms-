import type { ReactNode } from "react";

import { cn } from "@/core/lib/cn";
import { useInDrawer } from "./Drawer";

export function Card({ title, description, actions, children, className, bodyClassName }: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  // in a slide-over on a phone the panel is already the frame: no card border eating the width
  const flat = useInDrawer() !== null;
  return (
    <section className={cn("rounded-2xl border border-slate-200/80 bg-white shadow-card", flat && "max-sm:rounded-none max-sm:border-0 max-sm:bg-transparent max-sm:shadow-none", className)}>
      {(title || actions) && (
        <header className={cn("flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-5 py-4 sm:px-6", flat && "max-sm:px-0")}>
          <div>
            {title && <h2 className="text-[15px] font-bold text-navy-950">{title}</h2>}
            {typeof description !== "string" && description && <div className="mt-0.5 text-sm text-slate-500">{description}</div>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn("px-5 py-5 sm:px-6", flat && "max-sm:px-0", bodyClassName)}>{children}</div>
    </section>
  );
}
