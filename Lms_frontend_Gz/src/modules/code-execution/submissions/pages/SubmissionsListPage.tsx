import { useNavigate } from "react-router-dom";

import { useListParams } from "@/core/hooks/useListParams";
import { useListSubmissionsQuery } from "@/modules/code-execution/submissions/api/submissionsApi";
import { SubmissionFilters } from "@/modules/code-execution/submissions/components/list/SubmissionFilters";
import { useSubmissionColumns } from "@/modules/code-execution/submissions/components/list/useSubmissionColumns";
import type { SubmissionFilters as Filters } from "@/modules/code-execution/submissions/types";
import { Button, Card, DataTable, EmptyState, PageHeader, Pagination } from "@/shared/ui";

export function SubmissionsListPage() {
  const navigate = useNavigate();
  const { params, update, reset } = useListParams<Record<keyof Filters, string | undefined>>({ page: 1, per_page: 20 });
  const apiParams = params as Filters & { page: number; per_page: number };
  const { data, isFetching, isError, refetch } = useListSubmissionsQuery(apiParams);
  const columns = useSubmissionColumns();
  const activeCount = [apiParams.status, apiParams.verdict].filter(Boolean).length;

  return (
    <>
      <PageHeader title="My submissions" description="Every solution you've submitted, across every problem." />
      <Card bodyClassName="p-0">
        <SubmissionFilters filters={apiParams} activeCount={activeCount} update={update} reset={reset} />
        {isError ? (
          <EmptyState icon="alert" title="Could not load submissions" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={data?.items ?? []}
              rowKey={(item) => item.submission_id}
              loading={isFetching}
              onRowClick={(item) => navigate(`/submissions/${item.submission_id}`)}
              empty={<EmptyState icon="upload" title={activeCount ? "No matches" : "No submissions yet"} description={activeCount ? "Clear a filter to see more." : "Solve a problem and submit it to see results here."} />}
            />
            <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={(next) => update({ page: next })} onPerPageChange={(next) => update({ per_page: next })} />
          </>
        )}
      </Card>
    </>
  );
}
