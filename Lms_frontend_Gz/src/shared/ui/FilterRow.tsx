import { Children, useState, type ReactNode } from "react";

import { cn } from "@/core/lib/cn";
import { Button } from "./Button";

/**
 * A list's filter controls in one row. On a phone, several filters fold behind one "Filters" button so the
 * results stay on screen; a single filter just shows. Same spacing everywhere.
 */
export function FilterRow({ children, activeCount = 0, bordered = true }: { children: ReactNode; activeCount?: number; /** False when the row stands alone in its own card. */ bordered?: boolean }) {
  const [open, setOpen] = useState(false);
  const several = Children.toArray(children).filter(Boolean).length > 1;

  return (
    <div className={cn("px-5 py-4 sm:px-6", bordered && "border-b border-slate-100")}>
      {several && (
        <Button variant="secondary" icon="filter" className="w-full sm:hidden" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          {activeCount > 0 ? `Filters (${activeCount})` : open ? "Hide filters" : "Filters"}
        </Button>
      )}
      <div className={cn("flex-col gap-3 sm:flex sm:flex-row sm:flex-wrap sm:items-end", several ? (open ? "mt-3 flex" : "hidden") : "flex")}>{children}</div>
    </div>
  );
}
