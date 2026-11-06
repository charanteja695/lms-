import { useNavigate } from "react-router-dom";

import { useListParams } from "@/core/hooks/useListParams";
import { ProctoringTabs } from "@/modules/proctoring/common/components/ProctoringTabs";
import { useListCasesQuery } from "@/modules/proctoring/cases/api/casesApi";
import { CaseFilters } from "@/modules/proctoring/cases/components/list/CaseFilters";
import { useCaseColumns } from "@/modules/proctoring/cases/components/list/useCaseColumns";
import type { CaseFilters as Filters } from "@/modules/proctoring/cases/types";
import { Button, Card, DataTable, EmptyState, PageHeader, Pagination } from "@/shared/ui";

export function CasesListPage() {
  const navigate = useNavigate();
  const { params, update, reset } = useListParams<Record<keyof Filters, string | boolean | undefined>>({ page: 1, per_page: 20 });
  const apiParams = params as Filters & { page: number; per_page: number };
  const { data, isFetching, isError, refetch } = useListCasesQuery(apiParams);
  const columns = useCaseColumns();
  const activeCount = Object.entries(apiParams).filter(([key, value]) => !["page", "per_page"].includes(key) && value !== undefined && value !== "").length;

  return (
    <>
      <PageHeader title="Proctoring" description="Exam sessions that were not cleared automatically and need a person to decide." />
      <ProctoringTabs />
      <Card bodyClassName="p-0">
        <CaseFilters filters={apiParams} activeCount={activeCount} update={update} reset={reset} />
        {isError ? (
          <EmptyState icon="alert" title="Could not load cases" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={data?.items ?? []}
              rowKey={(item) => item.case_id}
              loading={isFetching}
              onRowClick={(item) => navigate(`/proctoring/cases/${item.case_id}`)}
              empty={<EmptyState icon="shield" title={activeCount ? "No matches" : "No cases"} description={activeCount ? "Clear a filter to see more." : "Exams that need a person's review appear here."} />}
            />
            <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={(next) => update({ page: next })} onPerPageChange={(next) => update({ per_page: next })} />
          </>
        )}
      </Card>
    </>
  );
}
