import { useNavigate } from "react-router-dom";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { formatDateTime } from "@/core/lib/format";
import { RecommendationBadge } from "@/modules/ai-interview/common/components/InterviewBadges";
import { useDecideAppealMutation, useListOpenAppealsQuery } from "@/modules/ai-interview/screening/api/screeningApi";
import { InterviewTabs } from "@/modules/ai-interview/screening/components/InterviewTabs";
import { UserNameCell } from "@/modules/user-management/common/components/UserNameCell";
import { Button, Card, ConfirmDialog, EmptyState, PageHeader, Spinner } from "@/shared/ui";

/** Candidates' appeals of a screening result. Decided by someone other than the original reviewer (SECOND_REVIEWER_REQUIRED). */
export function AppealsPage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const confirm = useConfirmAction();
  const { data, isFetching } = useListOpenAppealsQuery({ per_page: 50 });
  const [decide] = useDecideAppealMutation();
  const appeals = data?.items ?? [];

  const answer = (interviewId: string, uphold: boolean) =>
    confirm.ask(
      { title: uphold ? "Uphold the appeal?" : "Deny the appeal?", description: uphold ? "The candidate may retake the interview." : "A note explaining why is required.", confirmLabel: uphold ? "Uphold" : "Deny", tone: uphold ? "primary" : "danger", withReason: true },
      async (note) => {
        await decide({ interviewId, uphold, note }).unwrap().then(() => notify.success("Appeal decided"), notify.apiError);
      },
    );

  return (
    <>
      <PageHeader title="AI interviews" description="Candidates asking for a screening result to be looked at again. Someone other than the first reviewer decides." />
      <InterviewTabs />
      {isFetching && appeals.length === 0 ? <Spinner /> : appeals.length === 0 ? <EmptyState icon="check" title="No open appeals" description="When a candidate asks for a screening result to be looked at again, it appears here." /> : (
        <div className="space-y-3">
          {appeals.map((a) => (
            <Card key={a.appeal_id} title={<UserNameCell userId={a.user_id} />} description={`${a.interview.role} · appealed ${formatDateTime(a.created_at)}`} actions={<RecommendationBadge value={a.interview.final_recommendation} />}>
              <p className="whitespace-pre-wrap text-sm text-slate-700">{a.reason}</p>
              <div className="mt-3 flex justify-end gap-2">
                <Button size="sm" variant="ghost" onClick={() => navigate(`/interviews/screening/${a.interview_id}`)}>Open interview</Button>
                <Button size="sm" variant="secondary" onClick={() => answer(a.interview_id, false)}>Deny</Button>
                <Button size="sm" onClick={() => answer(a.interview_id, true)}>Uphold</Button>
              </div>
            </Card>
          ))}
        </div>
      )}
      <ConfirmDialog {...confirm.dialogProps} />
    </>
  );
}
