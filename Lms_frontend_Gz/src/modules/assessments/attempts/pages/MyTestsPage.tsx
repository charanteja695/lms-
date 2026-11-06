import { useNavigate } from "react-router-dom";

import { useListMyTestsQuery } from "@/modules/assessments/attempts/api/attemptsApi";
import { MyTestCard } from "@/modules/assessments/attempts/components/MyTestCard";
import { Button, EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function MyTestsPage() {
  const navigate = useNavigate();
  const { data: tests, isLoading, isError, refetch } = useListMyTestsQuery({});

  return (
    <>
      <PageHeader title="My tests" description="Tests you can take now, and why one isn't open yet." />
      {isLoading ? (
        <PageLoader />
      ) : isError ? (
        <EmptyState icon="alert" title="Could not load your tests" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
      ) : (tests?.length ?? 0) === 0 ? (
        <EmptyState
          icon="fileText"
          title="No tests for you yet"
          description="Tests appear here when your institution schedules them for a course you're enrolled in. Keep going with your lessons in the meantime."
          action={<Button onClick={() => navigate("/my-learning")}>Go to My learning</Button>}
        />
      ) : (
        <div className="space-y-4">
          {tests?.map((test) => <MyTestCard key={test.test_id} test={test} />)}
        </div>
      )}
    </>
  );
}
