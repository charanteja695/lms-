import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { Button } from "./Button";
import { useInDrawer } from "./Drawer";
import { Icon } from "./Icon";

export function PageHeader({ title, description, actions, backTo, backLabel = "Back" }: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  backTo?: string;
  backLabel?: string;
}) {
  const drawer = useInDrawer();
  if (drawer) {
    // In a slide-over: a compact header that stays put while the form scrolls, with its own close button.
    return (
      <div className="sticky top-0 z-10 -mx-5 -mt-6 mb-6 flex items-start justify-between gap-4 border-b border-slate-200/80 bg-white/95 px-5 py-4 backdrop-blur sm:-mx-8 sm:px-8">
        <div className="min-w-0">
          <h2 id={drawer.titleId} className="text-lg font-bold tracking-tight text-navy-950 sm:text-xl">{title}</h2>
          {typeof description !== "string" && description && <div className="mt-0.5 text-sm text-slate-500">{description}</div>}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {actions}
          <Button variant="ghost" size="icon" onClick={drawer.close} aria-label="Close">
            <Icon name="x" />
          </Button>
        </div>
      </div>
    );
  }
  return (
    <div className="mb-7 space-y-3">
      {backTo && (
        <Link to={backTo} className="inline-flex items-center gap-1 rounded-lg text-sm font-medium text-slate-500 transition-colors hover:text-brand-700">
          <Icon name="chevronLeft" size={16} />
          {backLabel}
        </Link>
      )}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold tracking-tight text-navy-950 sm:text-[28px]">{title}</h1>
          {typeof description !== "string" && description && <div className="mt-1.5 text-sm text-slate-500 sm:text-[15px]">{description}</div>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}
