import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useListParams } from "@/core/hooks/useListParams";
import { CodeTabs } from "@/modules/code-execution/common/components/CodeTabs";
import { DifficultyBadge } from "@/modules/code-execution/common/components/DifficultyBadge";
import { useListProblemsQuery } from "@/modules/code-execution/problems/api/problemsApi";
import { ProblemFilters } from "@/modules/code-execution/problems/components/list/ProblemFilters";
import { useProblemColumns } from "@/modules/code-execution/problems/components/list/useProblemColumns";
import type { ProblemFilters as Filters } from "@/modules/code-execution/problems/types";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { Button, Card, DataTable, EmptyState, Icon, PageHeader, Pagination, StatTile } from "@/shared/ui";

export function ProblemsListPage() {
  const navigate = useNavigate();
  const { can, isSuperAdmin } = useCan();
  const canAuthor = can("content.author") || isSuperAdmin;
  const [viewMode, setViewMode] = useState<"grid" | "table">("grid");
  const { params, update, reset } = useListParams<Record<keyof Filters, string | boolean | undefined>>({ page: 1, per_page: 20 });
  const apiParams = params as Filters & { page: number; per_page: number };
  const { data, isFetching, isError, refetch } = useListProblemsQuery(apiParams);
  const columns = useProblemColumns({ canAuthor });
  const { page: _page, per_page: _perPage, search, ...filterValues } = apiParams;
  const activeCount = Object.values({ ...filterValues, search }).filter((value) => value !== undefined && value !== "").length;

  const items = data?.items ?? [];
  const easyCount = useMemo(() => items.filter((p) => p.difficulty === "easy").length, [items]);
  const mediumCount = useMemo(() => items.filter((p) => p.difficulty === "medium").length, [items]);
  const hardCount = useMemo(() => items.filter((p) => p.difficulty === "hard").length, [items]);

  return (
    <>
      <PageHeader
        title="Coding practice"
        description="Solve coding and SQL problems. Every run is checked against the problem's test cases."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="secondary" icon="terminal" onClick={() => navigate("/compiler")}>
              Compiler
            </Button>
            {canAuthor && <Button icon="plus" onClick={() => navigate("/problems/new")}>New problem</Button>}
          </div>
        }
      />
      <CodeTabs />

      {/* Metrics Bar */}
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile icon="terminal" label="Total problems" value={data?.pageContext.total_records ?? items.length} />
        <StatTile icon="check" label="Easy problems" value={easyCount} />
        <StatTile icon="sparkles" label="Medium problems" value={mediumCount} />
        <StatTile icon="shield" label="Hard problems" value={hardCount} />
      </div>

      <Card bodyClassName="p-0">
        <div className="flex flex-wrap items-center justify-between border-b border-slate-200/80 px-4 py-3 gap-3">
          <div className="flex items-center gap-1 rounded-xl bg-slate-100 p-1">
            <button
              type="button"
              onClick={() => setViewMode("grid")}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all cursor-pointer ${
                viewMode === "grid" ? "bg-white text-navy-950 shadow-sm" : "text-slate-500 hover:text-slate-900"
              }`}
            >
              <Icon name="layers" size={14} /> Cards
            </button>
            <button
              type="button"
              onClick={() => setViewMode("table")}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all cursor-pointer ${
                viewMode === "table" ? "bg-white text-navy-950 shadow-sm" : "text-slate-500 hover:text-slate-900"
              }`}
            >
              <Icon name="menu" size={14} /> Table
            </button>
          </div>
        </div>

        <ProblemFilters filters={apiParams} canAuthor={canAuthor} activeCount={activeCount} update={update} reset={reset} />

        {isError ? (
          <EmptyState icon="alert" title="Could not load problems" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
        ) : items.length === 0 ? (
          <EmptyState
            icon="terminal"
            title={activeCount ? "No matches found" : "No coding problems yet"}
            description={activeCount ? "Clear a filter to see more problems." : "Coding and SQL problems appear here once published."}
            action={activeCount ? <Button variant="secondary" onClick={reset}>Reset filters</Button> : undefined}
          />
        ) : viewMode === "grid" ? (
          <div className="p-4 sm:p-6">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((problem) => (
                <div
                  key={problem.problem_id}
                  onClick={() => navigate(`/problems/${problem.problem_id}`)}
                  className="group flex flex-col justify-between rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card transition-all duration-200 hover:-translate-y-1 hover:border-brand-300 hover:shadow-lift cursor-pointer"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2">
                      <DifficultyBadge difficulty={problem.difficulty} />
                      <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                        {problem.problem_type}
                      </span>
                    </div>
                    <h3 className="mt-3 text-base font-bold text-navy-950 transition-colors group-hover:text-brand-700">
                      {problem.title}
                    </h3>
                    {problem.tags && problem.tags.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1">
                        {problem.tags.slice(0, 3).map((tag) => (
                          <span key={tag} className="rounded-md bg-slate-100 px-2 py-0.5 text-[10.5px] font-medium text-slate-600">
                            {tag}
                          </span>
                        ))}
                        {problem.tags.length > 3 && (
                          <span className="text-[10px] text-slate-400 self-center">
                            +{problem.tags.length - 3}
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-3 text-xs font-semibold text-brand-700">
                    <span className="inline-flex items-center gap-1">
                      <Icon name="terminal" size={13} />
                      Solve Problem
                    </span>
                    <Icon name="chevronRight" size={15} className="transition-transform group-hover:translate-x-0.5" />
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-6 border-t border-slate-100 pt-4">
              <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={(next) => update({ page: next })} onPerPageChange={(next) => update({ per_page: next })} />
            </div>
          </div>
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={items}
              rowKey={(item) => item.problem_id}
              loading={isFetching}
              onRowClick={(item) => navigate(`/problems/${item.problem_id}`)}
              empty={<EmptyState icon="terminal" title="No problems found" />}
            />
            <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={(next) => update({ page: next })} onPerPageChange={(next) => update({ per_page: next })} />
          </>
        )}
      </Card>
    </>
  );
}
