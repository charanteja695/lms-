import { useJobRights } from "@/modules/job-portal/common/hooks/useJobRights";
import { useNavigate, useParams } from "react-router-dom";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { formatDateTime } from "@/core/lib/format";
import { ApplicationStatusBadge, MatchBadge } from "@/modules/job-portal/common/components/JobBadges";
import { StageHistory } from "@/modules/job-portal/common/components/StageHistory";
import { TERMINAL_STATUSES } from "@/modules/job-portal/common/terminal";
import { useGetMyApplicationQuery, useWithdrawApplicationMutation } from "@/modules/job-portal/applications/api/myApplicationsApi";
import { NextActionBar } from "@/modules/job-portal/applications/components/NextActionBar";
import { OfferCard } from "@/modules/job-portal/applications/components/OfferCard";
import { ProgressSteps } from "@/modules/job-portal/applications/components/ProgressSteps";
import { Button, Card, ConfirmDialog, DescriptionList, EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function MyApplicationPage() {
  const { applicationId = "" } = useParams();
  const navigate = useNavigate();
  const { canWithdraw } = useJobRights();
  const notify = useNotify();
  const confirm = useConfirmAction();
  const { data: application, isLoading, isError } = useGetMyApplicationQuery(applicationId, { skip: !applicationId });
  const [withdraw] = useWithdrawApplicationMutation();

  if (isLoading) return <PageLoader />;
  if (isError || !application) return <EmptyState icon="alert" title="Application not found" />;
  const closed = TERMINAL_STATUSES.has(application.status);

  return (
    <>
      <PageHeader
        title={application.job_title}
        description={application.company_name ?? undefined}
        backTo="/jobs/applications"
        backLabel="My applications"
        actions={
          <div className="flex items-center gap-2">
            <ApplicationStatusBadge status={application.status} />
            <Button variant="secondary" size="sm" onClick={() => navigate(`/jobs/board/${application.job_id}`)}>View job</Button>
            {!closed && canWithdraw && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  confirm.ask({ title: "Withdraw this application?", description: "The company stops considering you for this job. This can't be undone.", confirmLabel: "Withdraw", withReason: true }, async (note) => {
                    await withdraw({ id: applicationId, note }).unwrap().catch(notify.apiError);
                  })
                }
              >
                Withdraw
              </Button>
            )}
          </div>
        }
      />
      <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
        <div className="space-y-4">
          <Card><div className="space-y-4"><ProgressSteps steps={application.progress} />{application.next_action?.kind !== "offer" && <NextActionBar application={application} />}</div></Card>
          {application.offer && <OfferCard applicationId={applicationId} offer={application.offer} />}
          <Card title="Progress"><StageHistory history={application.history} /></Card>
        </div>
        <div className="space-y-4">
          <Card title="Your match">
            <MatchBadge score={application.match_score} />
            {application.match_explanation && <ul className="mt-2 list-disc pl-5 text-sm text-slate-600">{application.match_explanation.map((line) => <li key={line}>{line}</li>)}</ul>}
          </Card>
          {application.assessment && (
            <Card title="Assessment">
              <DescriptionList
                columns={1}
                items={[
                  { label: "Status", value: application.assessment.invite_state },
                  { label: "Score", value: application.assessment.percent != null ? `${application.assessment.percent}%` : null },
                  { label: "Result", value: application.assessment.result },
                ]}
              />
              {application.assessment.invite_state === "sent" && application.assessment.percent == null && <Button size="sm" className="mt-3" onClick={() => navigate("/my-tests")}>Go to My tests</Button>}
            </Card>
          )}
          <p className="text-xs text-slate-400">Applied {formatDateTime(application.applied_at)} with resume version {application.resume_version_no}.</p>
        </div>
      </div>
      <ConfirmDialog {...confirm.dialogProps} />
    </>
  );
}
