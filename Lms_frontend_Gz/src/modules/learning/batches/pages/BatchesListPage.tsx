import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useListParams } from "@/core/hooks/useListParams";
import { useListBatchesQuery } from "@/modules/learning/batches/api/batchesApi";
import { BatchFilters } from "@/modules/learning/batches/components/list/BatchFilters";
import { useBatchColumns } from "@/modules/learning/batches/components/list/useBatchColumns";
import { BatchStatusBadge } from "@/modules/learning/common/components/BatchStatusBadge";
import type { BatchFilters as Filters } from "@/modules/learning/batches/types";
import { Button, Card, DataTable, EmptyState, Icon, PageHeader, Pagination, StatTile } from "@/shared/ui";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { formatDate } from "@/core/lib/format";

export function BatchesListPage() {
  const { can, acts } = useCan();
  const navigate = useNavigate();
  const canManage = can("accounts.manage") || acts("batches.create", "learning.batches.manage");  // "New batch"
  const [viewMode, setViewMode] = useState<"grid" | "table">("grid");

  const { params, update, reset } = useListParams<Record<keyof Filters, string | undefined>>({ page: 1, per_page: 20 });
  const apiParams = params as Filters & { page: number; per_page: number };
  const { data, isFetching, isError, refetch } = useListBatchesQuery(apiParams);
  const columns = useBatchColumns();
  const activeCount = apiParams.status ? 1 : 0;

  const batches = data?.items ?? [];

  const counts = useMemo(() => {
    let active = 0;
    let archived = 0;
    for (const b of batches) {
      if (b.status === "active") active++;
      else archived++;
    }
    return { active, archived };
  }, [batches]);

  return (
    <>
      <PageHeader
        title="Batches"
        description="Student cohorts taking a course curriculum together."
        actions={
          <div className="flex items-center gap-3">
            <div className="inline-flex rounded-xl bg-slate-100 p-1 ring-1 ring-slate-200/70">
              <button
                type="button"
                onClick={() => setViewMode("grid")}
                className={`flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs font-semibold transition-colors ${
                  viewMode === "grid" ? "bg-white text-navy-950 shadow-sm" : "text-slate-500 hover:text-slate-900"
                }`}
                title="Grid view"
              >
                <Icon name="layers" size={14} /> Cards
              </button>
              <button
                type="button"
                onClick={() => setViewMode("table")}
                className={`flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs font-semibold transition-colors ${
                  viewMode === "table" ? "bg-white text-navy-950 shadow-sm" : "text-slate-500 hover:text-slate-900"
                }`}
                title="Table view"
              >
                <Icon name="fileText" size={14} /> Table
              </button>
            </div>

            {canManage && (
              <Button icon="plus" onClick={() => navigate("/batches/new")}>
                New batch
              </Button>
            )}
          </div>
        }
      />

      {/* Top Stat Highlights */}
      <div className="mb-6 grid grid-cols-3 gap-3 sm:gap-4">
        <StatTile icon="layers" label="Total batches" value={data?.pageContext.total_records ?? batches.length} />
        <StatTile icon="check" label="Active cohorts" value={counts.active} />
        <StatTile icon="clock" label="Archived" value={counts.archived} />
      </div>

      <Card bodyClassName="p-0">
        <BatchFilters filters={apiParams} activeCount={activeCount} update={update} reset={reset} />

        {isError ? (
          <EmptyState
            icon="alert"
            title="Could not load batches"
            action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>}
          />
        ) : batches.length === 0 ? (
          <EmptyState
            icon="layers"
            title={activeCount ? "No matches" : "No batches yet"}
            description={
              activeCount
                ? "Clear filters to see all student batches."
                : "Create a batch to assign an enrolled course to students."
            }
            action={
              canManage && !activeCount ? (
                <Button icon="plus" onClick={() => navigate("/batches/new")}>
                  Create first batch
                </Button>
              ) : undefined
            }
          />
        ) : viewMode === "grid" ? (
          <div className="p-5 sm:p-6">
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {batches.map((batch) => (
                <div
                  key={batch.batch_id}
                  className="group flex flex-col justify-between overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-card transition-all duration-200 hover:-translate-y-1 hover:border-brand-300 hover:shadow-lift"
                >
                  <div>
                    {/* Header banner */}
                    <div className="relative h-18 w-full overflow-hidden bg-gradient-to-r from-ink-950 via-navy-900 to-ink-900 px-5 pt-3.5">
                      <div
                        className="absolute inset-0 bg-[radial-gradient(80%_100%_at_0%_0%,color-mix(in_oklab,var(--color-brand-500)_35%,transparent),transparent_70%)]"
                        aria-hidden="true"
                      />
                      <div className="relative flex items-center justify-between">
                        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white text-brand-600 shadow-sm ring-1 ring-slate-100">
                          <Icon name="layers" size={18} />
                        </span>
                        <BatchStatusBadge status={batch.status} />
                      </div>
                    </div>

                    <div className="p-5">
                      <Link
                        to={`/batches/${batch.batch_id}`}
                        className="line-clamp-2 text-base font-bold text-navy-950 transition-colors hover:text-brand-700"
                      >
                        {batch.name}
                      </Link>

                      <div className="mt-2 flex items-center gap-1.5 text-xs text-slate-600">
                        <Icon name="graduation" size={14} className="text-brand-600 shrink-0" />
                        <span className="truncate font-semibold text-slate-800">{batch.title}</span>
                      </div>

                      <p className="mt-3 text-xs text-slate-400">
                        Created {formatDate(batch.created_at.slice(0, 10))}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50/60 px-5 py-3">
                    <Link
                      to={`/batches/${batch.batch_id}`}
                      className="text-xs font-semibold text-brand-700 transition-colors hover:text-brand-800"
                    >
                      Manage roster & students →
                    </Link>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-6 border-t border-slate-100 pt-4">
              <Pagination
                pageContext={data?.pageContext}
                disabled={isFetching}
                onPageChange={(next) => update({ page: next })}
                onPerPageChange={(next) => update({ per_page: next })}
              />
            </div>
          </div>
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={batches}
              rowKey={(item) => item.batch_id}
              loading={isFetching}
              onRowClick={(item) => navigate(`/batches/${item.batch_id}`)}
            />
            <Pagination
              pageContext={data?.pageContext}
              disabled={isFetching}
              onPageChange={(next) => update({ page: next })}
              onPerPageChange={(next) => update({ per_page: next })}
            />
          </>
        )}
      </Card>
    </>
  );
}
