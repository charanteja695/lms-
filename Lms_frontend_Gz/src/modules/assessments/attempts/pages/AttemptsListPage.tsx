import { useNavigate } from "react-router-dom";

import { useListParams } from "@/core/hooks/useListParams";
import { useListAttemptsQuery } from "@/modules/assessments/attempts/api/attemptsApi";
import { AttemptFilters } from "@/modules/assessments/attempts/components/list/AttemptFilters";
import { useAttemptColumns } from "@/modules/assessments/attempts/components/list/useAttemptColumns";
import type { AttemptFilters as Filters } from "@/modules/assessments/attempts/types";
import { Button, Card, DataTable, EmptyState, PageHeader, Pagination } from "@/shared/ui";

export function AttemptsListPage() {
  const navigate = useNavigate();
  const { params, update, reset } = useListParams<Record<keyof Filters, string | boolean | undefined>>({ page: 1, per_page: 20 });
  const apiParams = params as Filters & { page: number; per_page: number };
  const { data, isFetching, isError, refetch } = useListAttemptsQuery(apiParams);
  const columns = useAttemptColumns();
  const activeCount = Object.entries(apiParams).filter(([key, value]) => !["page", "per_page", "sort_order"].includes(key) && value !== undefined && value !== "").length;

  return (
    <>
      <PageHeader title="Attempts" description="Every test attempt you may see, scoped to your role." />
      <Card bodyClassName="p-0">
        <AttemptFilters filters={apiParams} activeCount={activeCount} update={update} reset={reset} />
        {isError ? (
          <EmptyState icon="alert" title="Could not load attempts" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={data?.items ?? []}
              rowKey={(item) => item.attempt_id}
              loading={isFetching}
              onRowClick={(item) => navigate(`/attempts/${item.attempt_id}`)}
              empty={<EmptyState icon="users" title={activeCount ? "No matches" : "No attempts yet"} description={activeCount ? "Clear a filter to see more." : "Attempts appear here as students start tests."} />}
            />
            <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={(next) => update({ page: next })} onPerPageChange={(next) => update({ per_page: next })} />
          </>
        )}
      </Card>
    </>
  );
}
