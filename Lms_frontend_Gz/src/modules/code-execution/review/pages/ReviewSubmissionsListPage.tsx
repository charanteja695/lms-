import { useNavigate } from "react-router-dom";

import { useListParams } from "@/core/hooks/useListParams";
import { CodeTabs } from "@/modules/code-execution/common/components/CodeTabs";
import { useListReviewSubmissionsQuery } from "@/modules/code-execution/review/api/reviewApi";
import { ReviewFilters } from "@/modules/code-execution/review/components/list/ReviewFilters";
import { useReviewColumns } from "@/modules/code-execution/review/components/list/useReviewColumns";
import type { ReviewFilters as Filters } from "@/modules/code-execution/review/types";
import { Button, Card, DataTable, EmptyState, PageHeader, Pagination } from "@/shared/ui";

export function ReviewSubmissionsListPage() {
  const navigate = useNavigate();
  const { params, update, reset } = useListParams<Record<keyof Filters, string | boolean | undefined>>({ page: 1, per_page: 20 });
  const apiParams = params as Filters & { page: number; per_page: number };
  const { data, isFetching, isError, refetch } = useListReviewSubmissionsQuery(apiParams);
  const columns = useReviewColumns();
  const activeCount = Object.entries(apiParams).filter(([key, value]) => !["page", "per_page", "sort_order"].includes(key) && value !== undefined && value !== "").length;

  return (
    <>
      <PageHeader title="Coding practice" description="Every submission across every problem, with the plagiarism signal." />
      <CodeTabs />
      <Card bodyClassName="p-0">
        <ReviewFilters filters={apiParams} activeCount={activeCount} update={update} reset={reset} />
        {isError ? (
          <EmptyState icon="alert" title="Could not load submissions" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={data?.items ?? []}
              rowKey={(item) => item.submission_id}
              loading={isFetching}
              onRowClick={(item) => navigate(`/review/submissions/${item.submission_id}`)}
              empty={<EmptyState icon="upload" title={activeCount ? "No matches" : "No submissions yet"} description={activeCount ? "Clear a filter to see more." : "Solve a problem and submit it to see results here."} />}
            />
            <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={(next) => update({ page: next })} onPerPageChange={(next) => update({ per_page: next })} />
          </>
        )}
      </Card>
    </>
  );
}
