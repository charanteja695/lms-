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
    <section className={cn("rounded-xl border border-[#E5E7EB] bg-white shadow-xs", flat && "max-sm:rounded-none max-sm:border-0 max-sm:bg-transparent max-sm:shadow-none", className)}>
      {(title || actions) && (
        <header className={cn("flex flex-wrap items-start justify-between gap-3 border-b border-[#E5E7EB] px-5 py-4", flat && "max-sm:px-0")}>
          <div>
            {title && <h2 className="text-[16px] font-semibold text-[#111827]">{title}</h2>}
            {typeof description !== "string" && description && <div className="mt-0.5 text-[12px] text-[#64748B]">{description}</div>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn("p-5", flat && "max-sm:px-0", bodyClassName)}>{children}</div>
    </section>
  );
}
