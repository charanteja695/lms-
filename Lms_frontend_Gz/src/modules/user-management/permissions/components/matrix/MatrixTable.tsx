import { useState, type ReactNode } from "react";

import { cn } from "@/core/lib/cn";
import type { MatrixAction, MatrixPage, PageAction } from "@/modules/user-management/permissions/api/permissionAdminApi";
import type { PageGroup } from "@/modules/user-management/permissions/components/matrix/matrixModel";
import { Icon } from "@/shared/ui";

/**
 * The permission matrix: modules (collapsible) → pages as rows, actions as columns. A page without an action shows "—".
 * ``renderCell`` draws each box; ``renderRowEnd`` adds a trailing control (e.g. a row reset).
 */
export function MatrixTable({ groups, actions, renderCell, renderRowEnd, rowChanged }: {
  groups: PageGroup[];
  actions: MatrixAction[];
  renderCell: (page: MatrixPage, action: PageAction) => ReactNode;
  renderRowEnd?: (page: MatrixPage) => ReactNode;
  rowChanged?: (page: MatrixPage) => boolean;
}) {
  const [closed, setClosed] = useState<Set<string>>(new Set());
  const toggle = (title: string) => setClosed((prev) => {
    const next = new Set(prev);
    if (next.has(title)) next.delete(title);
    else next.add(title);
    return next;
  });
  const columns = actions.length + 1 + (renderRowEnd ? 1 : 0);

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] border-separate border-spacing-0 text-sm">
        <thead>
          <tr>
            <th scope="col" className="sticky left-0 z-10 border-b border-slate-200 bg-slate-50 px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Module / page</th>
            {actions.map((a) => (
              <th key={a.key} scope="col" className="w-[84px] border-b border-slate-200 bg-slate-50 px-2 py-3 text-center text-xs font-semibold uppercase tracking-wide text-slate-500">{a.label}</th>
            ))}
            {renderRowEnd && <th scope="col" className="w-20 border-b border-slate-200 bg-slate-50"><span className="sr-only">Reset</span></th>}
          </tr>
        </thead>
        {groups.map((group) => {
          const open = !closed.has(group.title);
          return (
            <tbody key={group.title}>
              <tr>
                <td colSpan={columns} className="border-b border-slate-100 bg-brand-50/40 p-0">
                  <button type="button" aria-expanded={open} onClick={() => toggle(group.title)} className="flex w-full items-center gap-2 px-4 py-2.5 text-left">
                    <Icon name="chevronDown" size={16} className={cn("text-brand-700 transition-transform", !open && "-rotate-90")} />
                    <span className="font-semibold text-slate-800">{group.title}</span>
                    <span className="text-xs text-slate-500">{group.pages.length} page{group.pages.length === 1 ? "" : "s"}</span>
                  </button>
                </td>
              </tr>
              {open && group.pages.map((page) => {
                const has = new Map(page.actions.map((a) => [a.action, a]));
                return (
                  <tr key={page.key} className="group/row">
                    <th scope="row" className="sticky left-0 z-10 border-b border-slate-100 bg-white px-4 py-2.5 text-left font-normal group-hover/row:bg-slate-50">
                      <span className="flex items-center gap-1.5 font-medium text-slate-800">
                        {page.label}
                        {rowChanged?.(page) && <span className="h-1.5 w-1.5 rounded-full bg-amber-500" aria-label="changed" />}
                      </span>
                      <span className="block text-xs text-slate-500">{page.description}</span>
                    </th>
                    {actions.map((a) => {
                      const action = has.get(a.key);
                      return (
                        <td key={a.key} className="border-b border-slate-100 px-2 py-2.5 text-center group-hover/row:bg-slate-50">
                          {action ? renderCell(page, action) : <span className="text-slate-300" aria-label={`${page.label} has no ${a.label}`}>—</span>}
                        </td>
                      );
                    })}
                    {renderRowEnd && <td className="border-b border-slate-100 px-2 text-right group-hover/row:bg-slate-50">{renderRowEnd(page)}</td>}
                  </tr>
                );
              })}
            </tbody>
          );
        })}
      </table>
    </div>
  );
}
