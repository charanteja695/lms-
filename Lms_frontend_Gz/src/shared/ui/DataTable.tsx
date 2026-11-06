import type { ReactNode } from "react";

import { cn } from "@/core/lib/cn";
import { EmptyState } from "./EmptyState";

export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  className?: string;
  /** Hide on small screens to keep tables readable on phones. */
  hideOnMobile?: boolean;
}

/** A column keyed "actions" holds a row's buttons: right-aligned, never wrapping, and clicking them never opens the row. */
const ACTIONS = "actions";
const actionsCell = "w-px whitespace-nowrap text-right";

export function DataTable<T>({ columns, rows, rowKey, loading, onRowClick, empty, rowClassName }: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  loading?: boolean;
  onRowClick?: (row: T) => void;
  empty?: ReactNode;
  rowClassName?: (row: T) => string | undefined;
}) {
  return (
    <div className="relative overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50/70">
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={cn("px-4 py-3 text-left text-[11px] font-bold uppercase tracking-[0.06em] text-slate-500 first:pl-5 last:pr-5 sm:first:pl-6 sm:last:pr-6", column.hideOnMobile && "hidden md:table-cell", column.key === ACTIONS && actionsCell, column.className)}
              >
                {column.key === ACTIONS && !column.header ? <span className="sr-only">Actions</span> : column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className={cn("divide-y divide-slate-100 bg-white", loading && "opacity-60")}>
          {loading && rows.length === 0
            ? Array.from({ length: 6 }).map((_, index) => (
                <tr key={index}>
                  {columns.map((column) => (
                    <td key={column.key} className={cn("px-4 py-3.5", column.hideOnMobile && "hidden md:table-cell")}>
                      <div className="h-4 w-3/4 animate-pulse rounded-md bg-slate-100" />
                    </td>
                  ))}
                </tr>
              ))
            : rows.map((row) => (
                <tr
                  key={rowKey(row)}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={cn("transition-colors duration-150", onRowClick && "cursor-pointer hover:bg-brand-50/40", rowClassName?.(row))}
                >
                  {columns.map((column) => (
                    <td key={column.key} className={cn("px-4 py-3.5 align-middle text-slate-700 first:pl-5 last:pr-5 sm:first:pl-6 sm:last:pr-6", column.hideOnMobile && "hidden md:table-cell", column.key === ACTIONS && actionsCell, column.className)}>
                      {column.key === ACTIONS ? (
                        <div className="inline-flex items-center justify-end gap-1" onClick={(event) => event.stopPropagation()}>
                          {column.render(row)}
                        </div>
                      ) : (
                        column.render(row)
                      )}
                    </td>
                  ))}
                </tr>
              ))}
        </tbody>
      </table>
      {!loading && rows.length === 0 && (empty ?? <EmptyState title="No records found" description="Try changing the filters." />)}
    </div>
  );
}
