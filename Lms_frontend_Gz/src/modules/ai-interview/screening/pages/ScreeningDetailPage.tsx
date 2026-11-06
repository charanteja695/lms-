import { useState } from "react";
import { useParams } from "react-router-dom";

import { InterviewStatusBadge } from "@/modules/ai-interview/common/components/InterviewBadges";
import { TranscriptView } from "@/modules/ai-interview/common/components/TranscriptView";
import { useGetScreeningInterviewQuery } from "@/modules/ai-interview/screening/api/screeningApi";
import { CalibrationSampleDialog } from "@/modules/ai-interview/screening/components/CalibrationSampleDialog";
import { EvaluationCard } from "@/modules/ai-interview/screening/components/EvaluationCard";
import { ReviewCard } from "@/modules/ai-interview/screening/components/ReviewCard";
import { UserNameCell } from "@/modules/user-management/common/components/UserNameCell";
import { Alert, Button, Card, EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function ScreeningDetailPage() {
  const { interviewId = "" } = useParams();
  const { data: interview, isLoading, isError } = useGetScreeningInterviewQuery(interviewId);
  const [sampling, setSampling] = useState(false);

  if (isLoading) return <PageLoader />;
  if (isError || !interview) return <EmptyState icon="alert" title="Interview not found" />;

  return (
    <>
      <PageHeader
        title={<UserNameCell userId={interview.user_id} />}
        description={<span className="flex items-center gap-2"><InterviewStatusBadge status={interview.status} /> {interview.role} · attempt {interview.attempt_no}</span>}
        backTo="/interviews/screening"
        backLabel="Screening interviews"
        actions={interview.evaluation && interview.reviewed_at && <Button variant="secondary" onClick={() => setSampling(true)}>Add as calibration sample</Button>}
      />
      {interview.integrity_status === "invalidated" && <Alert tone="error" className="mb-4" title="Proctoring invalidated this interview">The recommendation is capped at "lean no".</Alert>}
      <div className="grid gap-4 lg:grid-cols-[1fr_24rem]">
        <Card title="Transcript"><div className="max-h-[70vh] overflow-y-auto bg-slate-50 p-3"><TranscriptView turns={interview.transcript} /></div></Card>
        <div className="space-y-4">
          <EvaluationCard interviewId={interviewId} evaluation={interview.evaluation} />
          <ReviewCard interview={interview} />
        </div>
      </div>
      {sampling && <CalibrationSampleDialog interview={interview} onClose={() => setSampling(false)} />}
    </>
  );
}
