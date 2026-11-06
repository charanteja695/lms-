import type { ReactNode } from "react";

import { cn } from "@/core/lib/cn";
import { useInDrawer } from "@/shared/ui/Drawer";

/** A form's Cancel / Save row. In a drawer it sticks to the bottom so Save is always in reach. */
export function FormActions({ children, className }: { children: ReactNode; className?: string }) {
  const inDrawer = useInDrawer() !== null;
  return (
    <div
      className={cn(
        "flex flex-wrap justify-end gap-3",
        inDrawer && "sticky bottom-0 z-10 -mx-5 -mb-6 mt-8 border-t border-slate-200/80 bg-white/95 px-5 py-4 backdrop-blur sm:-mx-8 sm:px-8",
        className,
      )}
    >
      {children}
    </div>
  );
}
