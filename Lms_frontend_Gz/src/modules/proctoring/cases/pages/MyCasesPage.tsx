import { useListMyCasesQuery } from "@/modules/proctoring/cases/api/casesApi";
import { MyCaseCard } from "@/modules/proctoring/cases/components/MyCaseCard";
import { Button, EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function MyCasesPage() {
  const { data: cases, isLoading, isError, refetch } = useListMyCasesQuery();

  return (
    <>
      <PageHeader title="Exam reviews" description="Proctored exams of yours that a person is reviewing, the decision, and your appeal." />
      {isLoading ? (
        <PageLoader />
      ) : isError ? (
        <EmptyState icon="alert" title="Could not load your cases" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
      ) : (cases?.length ?? 0) === 0 ? (
        <EmptyState icon="shield" title="No integrity cases" description="If an exam of yours needs a review, it appears here with what happens next." />
      ) : (
        <div className="space-y-4">
          {cases?.map((studentCase) => <MyCaseCard key={studentCase.case_id} studentCase={studentCase} />)}
        </div>
      )}
    </>
  );
}
