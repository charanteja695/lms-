import { Link, useLocation } from "react-router-dom";

import { cn } from "@/core/lib/cn";
import { Icon, type IconName } from "./Icon";

export interface SectionTab {
  to: string;
  label: string;
  icon?: IconName;
  /** Leave out a tab this person cannot use (the module's rights hook decides). */
  show?: boolean;
}

/**
 * Moving between a module's own pages, as tabs under the page title (not a row of header buttons, which are kept
 * for real actions). The longest matching path is the active one; scrolls sideways on a phone instead of wrapping.
 */
export function SectionTabs({ tabs }: { tabs: SectionTab[] }) {
  const { pathname } = useLocation();
  const visible = tabs.filter((t) => t.show !== false);
  if (visible.length < 2) return null;
  const active = visible.filter((t) => pathname === t.to || pathname.startsWith(`${t.to}/`)).sort((a, b) => b.to.length - a.to.length)[0];

  return (
    <nav aria-label="Section" className="-mt-2 mb-6 overflow-x-auto border-b border-slate-200">
      <ul className="flex min-w-max gap-1">
        {visible.map((t) => {
          const on = t === active;
          return (
            <li key={t.to}>
              <Link
                to={t.to}
                aria-current={on ? "page" : undefined}
                className={cn(
                  "-mb-px flex items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors",
                  on ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-800",
                )}
              >
                {t.icon && <Icon name={t.icon} size={16} />}
                {t.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
