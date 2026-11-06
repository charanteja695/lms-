import { useNavigate, useParams } from "react-router-dom";

import { ProblemTitleCell } from "@/modules/code-execution/problems/components/ProblemTitleCell";
import { useGetSubmissionQuery } from "@/modules/code-execution/submissions/api/submissionsApi";
import { SubmissionResultPanel } from "@/modules/code-execution/submissions/components/SubmissionResultPanel";
import { Button, Card, CodeEditor, EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function SubmissionDetailPage() {
  const { submissionId = "" } = useParams();
  const navigate = useNavigate();
  const { data: submission, isLoading, isError } = useGetSubmissionQuery({ submissionId }, { skip: !submissionId });

  if (isLoading) return <PageLoader />;
  if (isError || !submission) {
    return <EmptyState icon="alert" title="Submission not found" action={<Button onClick={() => navigate("/submissions")}>Back to submissions</Button>} />;
  }

  return (
    <>
      <PageHeader
        backTo="/submissions"
        backLabel="My submissions"
        title={<ProblemTitleCell problemId={submission.problem_id} />}
        description={submission.language}
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Your code">
          <CodeEditor value={submission.source} onChange={() => undefined} language={submission.language} rows={20} disabled />
        </Card>
        <SubmissionResultPanel submission={submission} isSubmitting={false} />
      </div>
    </>
  );
}
