import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { useNavigate, useParams } from "react-router-dom";

import { formatDateTime } from "@/core/lib/format";
import { useGetAttemptStateQuery } from "@/modules/assessments/attempts/api/attemptsApi";
import { AttemptControls } from "@/modules/assessments/attempts/components/detail/AttemptControls";
import { AttemptEventsCard } from "@/modules/assessments/attempts/components/detail/AttemptEventsCard";
import { AttemptStatusBadge } from "@/modules/assessments/common/components/AttemptStatusBadge";
import { Button, DescriptionList, EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function AttemptDetailPage() {
  const { attemptId = "" } = useParams();
  const { can, holds, acts } = useCan();
  const canControl = can("exams.manage") || holds("assessments.manage") || acts("attempts.update", "assessments.grade");
  const navigate = useNavigate();
  const { data: attempt, isLoading, isError } = useGetAttemptStateQuery(attemptId, { skip: !attemptId });

  if (isLoading) return <PageLoader />;
  if (isError || !attempt) {
    return <EmptyState icon="alert" title="Attempt not found" action={<Button onClick={() => navigate("/attempts")}>Back to attempts</Button>} />;
  }

  return (
    <>
      <PageHeader
        backTo="/attempts"
        backLabel="Attempts"
        title={
          <span className="flex flex-wrap items-center gap-3">
            {attempt.test_title}
            <AttemptStatusBadge status={attempt.status} />
          </span>
        }
        description={`Attempt #${attempt.attempt_no}`}
        actions={canControl ? <AttemptControls attemptId={attempt.attempt_id} status={attempt.status} /> : undefined}
      />
      <DescriptionList
        items={[
          { label: "Started", value: attempt.started_at ? formatDateTime(attempt.started_at) : null },
          { label: "Submitted", value: attempt.submitted_at ? formatDateTime(attempt.submitted_at) : null },
          { label: "Submit reason", value: attempt.submit_reason },
          { label: "Resumes", value: attempt.resume_count },
        ]}
      />
      <div className="mt-6">
        <AttemptEventsCard attemptId={attemptId} />
      </div>
    </>
  );
}
