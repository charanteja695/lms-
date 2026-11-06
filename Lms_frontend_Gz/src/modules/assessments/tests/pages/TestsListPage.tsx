import { useNavigate } from "react-router-dom";

import { useListParams } from "@/core/hooks/useListParams";
import { useListTestsQuery } from "@/modules/assessments/tests/api/testsApi";
import { TestFilters } from "@/modules/assessments/tests/components/list/TestFilters";
import { useTestColumns } from "@/modules/assessments/tests/components/list/useTestColumns";
import type { TestFilters as Filters } from "@/modules/assessments/tests/types";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { Button, Card, DataTable, EmptyState, PageHeader, Pagination } from "@/shared/ui";

export function TestsListPage() {
  const navigate = useNavigate();
  const { can, holds, isSuperAdmin } = useCan();
  const canAuthor = can("content.author") || isSuperAdmin || holds("assessments.author");
  const { params, update, reset } = useListParams<Record<keyof Filters, string | undefined>>({ page: 1, per_page: 20 });
  const apiParams = params as Filters & { page: number; per_page: number };
  const { data, isFetching, isError, refetch } = useListTestsQuery(apiParams);
  const columns = useTestColumns();
  const { page: _page, per_page: _perPage, search, ...filterValues } = apiParams;
  const activeCount = Object.values({ ...filterValues, search }).filter(Boolean).length;

  return (
    <>
      <PageHeader
        title="Tests"
        description="Topic, module and final tests, practice tests, and hiring assessments."
        actions={
          canAuthor && (
            <Button icon="plus" onClick={() => navigate("/tests/new")}>
              New test
            </Button>
          )
        }
      />
      <Card bodyClassName="p-0">
        <TestFilters filters={apiParams} activeCount={activeCount} update={update} reset={reset} />
        {isError ? (
          <EmptyState icon="alert" title="Could not load tests" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={data?.items ?? []}
              rowKey={(item) => item.test_id}
              loading={isFetching}
              onRowClick={(item) => navigate(`/tests/${item.test_id}`)}
              empty={<EmptyState icon="graduation" title={activeCount ? "No matches" : "No tests yet"} description={activeCount ? "Clear a filter to see more." : "Create a test from your questions."} />}
            />
            <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={(next) => update({ page: next })} onPerPageChange={(next) => update({ per_page: next })} />
          </>
        )}
      </Card>
    </>
  );
}
