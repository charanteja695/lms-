import type { ReactNode } from "react";

import { Icon, type IconName } from "./Icon";

export function EmptyState({ icon = "search", title, description, action }: {
  icon?: IconName;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <div className="relative mb-4">
        <div className="absolute inset-0 -m-2 rounded-full bg-brand-50" aria-hidden="true" />
        <div className="relative flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-brand-600 shadow-card ring-1 ring-slate-200/80">
          <Icon name={icon} size={22} />
        </div>
      </div>
      <p className="font-semibold text-navy-950">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
