import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useListParams } from "@/core/hooks/useListParams";
import { useListLearningPathsQuery } from "@/modules/catalog/learning-paths/api/learningPathsApi";
import { LearningPathFilters } from "@/modules/catalog/learning-paths/components/list/LearningPathFilters";
import { useLearningPathColumns } from "@/modules/catalog/learning-paths/components/list/useLearningPathColumns";
import { ContentStatusBadge } from "@/modules/catalog/common/components/ContentStatusBadge";
import type { LearningPathFilters as Filters } from "@/modules/catalog/learning-paths/types";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { Button, Card, DataTable, EmptyState, Icon, PageHeader, Pagination, StatTile } from "@/shared/ui";

export function LearningPathsListPage() {
  const navigate = useNavigate();
  const { can } = useCan();
  const canAuthor = can("content.author");
  const [viewMode, setViewMode] = useState<"grid" | "table">("grid");

  const { params, update, reset } = useListParams<Record<keyof Filters, string | undefined>>({ page: 1, per_page: 20 });
  const apiParams = params as Filters & { page: number; per_page: number };
  const { data, isFetching, isError, refetch } = useListLearningPathsQuery(apiParams);
  const columns = useLearningPathColumns({ canAuthor, onEdit: (path) => navigate(`/learning-paths/${path.learning_path_id}/edit`) });
  const { page: _page, per_page: _perPage, search_text, sort_order, ...filterValues } = apiParams;
  const activeCount = Object.values({ ...filterValues, search_text }).filter(Boolean).length;

  const paths = data?.items ?? [];

  const counts = useMemo(() => {
    let published = 0;
    let draft = 0;
    let inReview = 0;
    for (const p of paths) {
      if (p.status === "published") published++;
      else if (p.status === "draft") draft++;
      else if (p.status === "in_review") inReview++;
    }
    return { published, draft, inReview };
  }, [paths]);

  return (
    <>
      <PageHeader
        title="Learning paths"
        description="Structured curriculum paths connecting multiple courses towards a mastery goal."
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
                <Icon name="map" size={14} /> Cards
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

            {canAuthor && (
              <Button icon="plus" onClick={() => navigate("/learning-paths/new")}>
                New learning path
              </Button>
            )}
          </div>
        }
      />

      {/* Top Stat Highlights */}
      <div className="mb-6 grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatTile icon="map" label="Total paths" value={data?.pageContext.total_records ?? paths.length} />
        <StatTile icon="check" label="Published" value={counts.published} />
        <StatTile icon="clock" label="In review" value={counts.inReview} />
        <StatTile icon="edit" label="Drafts" value={counts.draft} />
      </div>

      <Card bodyClassName="p-0">
        <LearningPathFilters filters={apiParams} activeCount={activeCount} update={update} reset={reset} />

        {isError ? (
          <EmptyState
            icon="alert"
            title="Could not load learning paths"
            action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>}
          />
        ) : paths.length === 0 ? (
          <EmptyState
            icon="map"
            title={activeCount ? "No matches" : "No learning paths yet"}
            description={activeCount ? "Clear a filter to see more." : "Group courses into a path towards a career or certification goal."}
            action={
              canAuthor && !activeCount ? (
                <Button icon="plus" onClick={() => navigate("/learning-paths/new")}>
                  Create first path
                </Button>
              ) : undefined
            }
          />
        ) : viewMode === "grid" ? (
          <div className="p-5 sm:p-6">
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {paths.map((path) => (
                <div
                  key={path.learning_path_id}
                  className="group flex flex-col justify-between overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-card transition-all duration-200 hover:-translate-y-1 hover:border-brand-300 hover:shadow-lift"
                >
                  <div>
                    {/* Header gradient banner */}
                    <div className="relative h-20 w-full overflow-hidden bg-gradient-to-r from-ink-950 via-navy-900 to-ink-900 px-5 pt-4">
                      <div
                        className="absolute inset-0 bg-[radial-gradient(80%_100%_at_0%_0%,color-mix(in_oklab,var(--color-navy-400)_35%,transparent),transparent_70%)]"
                        aria-hidden="true"
                      />
                      <div className="relative flex items-center justify-between">
                        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-navy-800 shadow-sm ring-1 ring-slate-100">
                          <Icon name="map" size={20} />
                        </span>
                        <ContentStatusBadge status={path.status} />
                      </div>
                    </div>

                    <div className="p-5">
                      <Link
                        to={`/learning-paths/${path.learning_path_id}`}
                        className="line-clamp-2 text-base font-bold text-navy-950 transition-colors hover:text-brand-700"
                      >
                        {path.title}
                      </Link>
                      <p className="mt-1 font-mono text-xs text-slate-400">/{path.slug}</p>

                      {path.description && (
                        <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-slate-600">
                          {path.description}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50/60 px-5 py-3">
                    <Link
                      to={`/learning-paths/${path.learning_path_id}`}
                      className="text-xs font-semibold text-brand-700 transition-colors hover:text-brand-800"
                    >
                      View curriculum path →
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
              rows={paths}
              rowKey={(item) => item.learning_path_id}
              loading={isFetching}
              onRowClick={(item) => navigate(`/learning-paths/${item.learning_path_id}`)}
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
