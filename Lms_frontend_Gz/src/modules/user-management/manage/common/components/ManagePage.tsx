import type { ReactNode } from "react";

import type { PageContext } from "@/core/api/types";
import { Button, Card, EmptyState, FilterRow, PageHeader, Pagination } from "@/shared/ui";

/**
 * One User management screen: title with its count, a one-line description and the "Add …" button, then a
 * card holding the filters, the table and paging. Every screen of the section looks the same.
 */
export function ManagePage({ title, description, pageContext, addLabel, onAdd, filters, activeFilters, isError, onRetry, isFetching, onPageChange, onPerPageChange, children }: {
  title: string;
  description: string;
  pageContext?: PageContext;
  /** Shown only when the server lets this person create one. */
  addLabel?: string;
  onAdd?: () => void;
  filters: ReactNode;
  activeFilters: number;
  isError: boolean;
  onRetry: () => void;
  isFetching: boolean;
  onPageChange: (page: number) => void;
  onPerPageChange: (perPage: number) => void;
  children: ReactNode;
}) {
  const total = pageContext?.total_records;
  return (
    <>
      <PageHeader
        title={
          <span className="inline-flex items-center gap-3">
            {title}
            {total !== undefined && <span className="rounded-full bg-slate-200/80 px-2.5 py-0.5 text-sm font-bold text-slate-700">{total}</span>}
          </span>
        }
        description={description}
        actions={addLabel && onAdd ? <Button icon="plus" onClick={onAdd}>{addLabel}</Button> : undefined}
      />
      <Card bodyClassName="p-0">
        <FilterRow activeCount={activeFilters}>{filters}</FilterRow>
        {isError ? (
          <EmptyState icon="alert" title={`Could not load ${title.toLowerCase()}`} description="Check your connection and try again." action={<Button variant="secondary" onClick={onRetry}>Try again</Button>} />
        ) : (
          <>
            {children}
            <Pagination pageContext={pageContext} disabled={isFetching} onPageChange={onPageChange} onPerPageChange={onPerPageChange} />
          </>
        )}
      </Card>
    </>
  );
}
