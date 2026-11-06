import { useNavigate, useParams } from "react-router-dom";

import { useGetResultQuery } from "@/modules/assessments/attempts/api/attemptsApi";
import { ResultHero } from "@/modules/assessments/attempts/components/result/ResultHero";
import { ReviewList } from "@/modules/assessments/attempts/components/result/ReviewList";
import { Alert, Button, EmptyState, PageHeader, PageLoader } from "@/shared/ui";

const NOTEWORTHY_INTEGRITY_STATUSES = new Set(["flagged", "under_review", "invalidated"]);

export function AttemptResultPage() {
  const { attemptId = "" } = useParams();
  const navigate = useNavigate();
  const { data: result, isLoading, isError } = useGetResultQuery(attemptId, { skip: !attemptId });

  if (isLoading) return <PageLoader />;
  if (isError || !result) {
    return <EmptyState icon="alert" title="Could not load this result" action={<Button onClick={() => navigate("/my-tests")}>Back to my tests</Button>} />;
  }

  if (!result.released) {
    return (
      <>
        <PageHeader title={result.test_title} backTo="/my-tests" backLabel="My tests" />
        <Alert tone="info" title="Submitted">
          {result.message ?? "Your result will be released once it's ready."}
        </Alert>
      </>
    );
  }

  return (
    <div className="space-y-6">
      <ResultHero result={result} />
      {result.integrity_status && NOTEWORTHY_INTEGRITY_STATUSES.has(result.integrity_status) && (
        <Alert
          tone={result.integrity_status === "invalidated" ? "error" : "warning"}
          title={result.integrity_status === "invalidated" ? "This attempt was invalidated" : "This attempt is under integrity review"}
        >
          <Button variant="secondary" size="sm" onClick={() => navigate("/proctoring/my-cases")}>
            View my cases
          </Button>
        </Alert>
      )}

      {result.questions && result.questions.length > 0 && <ReviewList questions={result.questions} />}
    </div>
  );
}
