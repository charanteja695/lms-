import type { ReactNode } from "react";

import { cn } from "@/core/lib/cn";
import { Icon } from "@/shared/ui";

/** role = their role gives it · none = it doesn't · add = allowed for this person only · remove = removed for them only */
export type BoxState = "role" | "none" | "add" | "remove";

export const stateOf = (fromRole: boolean, override: boolean | null): BoxState =>
  override === true ? (fromRole ? "role" : "add") : override === false ? (fromRole ? "remove" : "none") : fromRole ? "role" : "none";

const STYLES: Record<BoxState, string> = {
  role: "border-[1.5px] border-brand-600 bg-brand-50 text-brand-800",
  none: "border-[1.5px] border-slate-300 bg-white text-transparent",
  add: "bg-brand-700 text-white",
  remove: "bg-red-600 text-white",
};

const MARK: Record<BoxState, ReactNode> = {
  role: <Icon name="check" size={15} />,
  none: null,
  add: <Icon name="plus" size={15} />,
  remove: <span className="text-base font-bold leading-none">−</span>,
};

const SAYS: Record<BoxState, string> = { role: "allowed by role", none: "not allowed", add: "allowed for this person only", remove: "removed for this person only" };

export function PersonBox({ state, unsaved, label, onClick }: { state: BoxState; unsaved: boolean; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={`${label} (${SAYS[state]})`}
      aria-label={`${label}: ${SAYS[state]}. Click to change.`}
      className={cn("relative inline-flex h-8 w-8 items-center justify-center rounded-lg transition-colors hover:ring-2 hover:ring-brand-200", STYLES[state])}
    >
      {MARK[state]}
      {unsaved && <span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-amber-500" aria-hidden="true" />}
    </button>
  );
}

export function PersonLegend({ name }: { name: string }) {
  const items: [BoxState, string][] = [["role", "Allowed by role"], ["none", "Not allowed"], ["add", `Allowed for ${name} only`], ["remove", `Removed for ${name} only`]];
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-slate-100 px-4 py-3 text-xs text-slate-600">
      {items.map(([state, text]) => (
        <span key={state} className="inline-flex items-center gap-2">
          <span className={cn("inline-flex h-5 w-5 items-center justify-center rounded-md [&_svg]:h-3 [&_svg]:w-3", STYLES[state])}>{MARK[state]}</span>
          {text}
        </span>
      ))}
      <span className="text-slate-400 sm:ml-auto">Click a box to change it; click again to follow the role.</span>
    </div>
  );
}
