import { useGetValidationQuery } from "@/modules/assessments/tests/api/testsApi";
import { Alert, Card } from "@/shared/ui";

export function ValidationCard({ testId }: { testId: string }) {
  const { data: validation, isFetching } = useGetValidationQuery(testId);
  if (isFetching && !validation) return null;
  if (!validation) return null;

  return (
    <Card title="Readiness to publish">
      {validation.valid ? (
        <Alert tone="success" title="Ready to publish">
          {validation.question_count} question{validation.question_count === 1 ? "" : "s"}, {validation.total_marks} total marks.
        </Alert>
      ) : (
        <div className="space-y-2">
          {validation.issues.map((issue, index) => (
            <Alert key={index} tone="warning" title={issue.field}>
              {issue.message}
            </Alert>
          ))}
        </div>
      )}
    </Card>
  );
}
