import { useNavigate } from "react-router-dom";

import { useListParams } from "@/core/hooks/useListParams";
import { useListQuestionsQuery } from "@/modules/assessments/questions/api/questionsApi";
import { QuestionFilters } from "@/modules/assessments/questions/components/list/QuestionFilters";
import { useQuestionColumns } from "@/modules/assessments/questions/components/list/useQuestionColumns";
import type { QuestionFilters as Filters } from "@/modules/assessments/questions/types";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { Button, Card, DataTable, EmptyState, PageHeader, Pagination } from "@/shared/ui";

export function QuestionsListPage() {
  const navigate = useNavigate();
  const { can, holds, isSuperAdmin } = useCan();
  const canAuthor = can("content.author") || isSuperAdmin || holds("assessments.author");
  const { params, update, reset } = useListParams<Record<keyof Filters, string | undefined>>({ page: 1, per_page: 20 });
  const apiParams = params as Filters & { page: number; per_page: number };
  const { data, isFetching, isError, refetch } = useListQuestionsQuery(apiParams);
  const columns = useQuestionColumns();
  const { page: _page, per_page: _perPage, search, ...filterValues } = apiParams;
  const activeCount = Object.values({ ...filterValues, search }).filter(Boolean).length;

  return (
    <>
      <PageHeader
        title="Question bank"
        description="Reusable questions for tests."
        actions={
          canAuthor && (
            <>
              <Button variant="secondary" icon="upload" onClick={() => navigate("/questions/import")}>Import</Button>
              <Button icon="plus" onClick={() => navigate("/questions/new")}>New question</Button>
            </>
          )
        }
      />
      <Card bodyClassName="p-0">
        <QuestionFilters filters={apiParams} activeCount={activeCount} update={update} reset={reset} />
        {isError ? (
          <EmptyState icon="alert" title="Could not load questions" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={data?.items ?? []}
              rowKey={(item) => item.question_id}
              loading={isFetching}
              onRowClick={(item) => navigate(`/questions/${item.question_id}`)}
              empty={<EmptyState icon="helpCircle" title={activeCount ? "No matches" : "No questions yet"} description={activeCount ? "Clear a filter to see more." : "Write a question or import a file to build your bank."} />}
            />
            <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={(next) => update({ page: next })} onPerPageChange={(next) => update({ per_page: next })} />
          </>
        )}
      </Card>
    </>
  );
}
