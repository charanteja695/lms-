import { useNavigate, useParams } from "react-router-dom";

import { ProblemTitleCell } from "@/modules/code-execution/problems/components/ProblemTitleCell";
import { useGetReviewSubmissionQuery } from "@/modules/code-execution/review/api/reviewApi";
import { SimilarMatchesCard } from "@/modules/code-execution/review/components/SimilarMatchesCard";
import { SubmissionResultPanel } from "@/modules/code-execution/submissions/components/SubmissionResultPanel";
import { UserNameCell } from "@/modules/user-management/common/components/UserNameCell";
import { Alert, Badge, Button, Card, CodeEditor, DescriptionList, EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function ReviewSubmissionDetailPage() {
  const { submissionId = "" } = useParams();
  const navigate = useNavigate();
  const { data: submission, isLoading, isError } = useGetReviewSubmissionQuery(submissionId, { skip: !submissionId });

  if (isLoading) return <PageLoader />;
  if (isError || !submission) {
    return <EmptyState icon="alert" title="Submission not found" action={<Button onClick={() => navigate("/review/submissions")}>Back to review</Button>} />;
  }

  return (
    <>
      <PageHeader
        backTo="/review/submissions"
        backLabel="Review submissions"
        title={
          <span className="flex flex-wrap items-center gap-3">
            <ProblemTitleCell problemId={submission.problem_id} />
            {submission.flagged && <Badge tone="red">Flagged</Badge>}
          </span>
        }
        description={
          <span>
            <UserNameCell userId={submission.user_id} /> · {submission.language}
          </span>
        }
      />

      {submission.flagged && (
        <Alert tone="warning" title={`${submission.similarity_percent}% similar to another submission`} className="mb-6">
          A signal for you to review, never an automatic decision.
        </Alert>
      )}

      <DescriptionList items={[{ label: "Exam reference", value: submission.reference }]} />

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <Card title="Code">
            <CodeEditor value={submission.source} onChange={() => undefined} language={submission.language} rows={20} disabled />
          </Card>
          <SimilarMatchesCard submissionId={submissionId} />
        </div>
        <SubmissionResultPanel submission={submission} isSubmitting={false} />
      </div>
    </>
  );
}
