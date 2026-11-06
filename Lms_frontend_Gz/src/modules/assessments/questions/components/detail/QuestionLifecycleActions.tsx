import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import {
  useApproveQuestionMutation,
  useDeleteDraftMutation,
  useRestoreQuestionMutation,
  useRetireQuestionMutation,
  useSubmitQuestionMutation,
} from "@/modules/assessments/questions/api/questionsApi";
import { RejectQuestionDialog } from "@/modules/assessments/questions/components/detail/RejectQuestionDialog";
import type { Question } from "@/modules/assessments/questions/types";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { Button, ConfirmDialog } from "@/shared/ui";

export function QuestionLifecycleActions({ question, canAuthor, canReview }: { question: Question; canAuthor: boolean; canReview: boolean }) {
  const navigate = useNavigate();
  const notify = useNotify();
  const confirm = useConfirmAction();
  const { user, role } = useAuth();
  const [submit, { isLoading: submitting }] = useSubmitQuestionMutation();
  const [approve, { isLoading: approving }] = useApproveQuestionMutation();
  const [deleteDraft] = useDeleteDraftMutation();
  const [retire] = useRetireQuestionMutation();
  const [restore] = useRestoreQuestionMutation();
  const [rejecting, setRejecting] = useState(false);

  const run = async (work: () => Promise<unknown>, success: string) => {
    try {
      await work();
      notify.success(success);
    } catch (error) {
      notify.apiError(error);
    }
  };

  const working = question.working;
  // "Someone other than the author must approve" — super admins are exempt from that check.
  const canReviewThis = canReview && Boolean(working) && (role === "super_admin" || working?.created_by !== user?.user_id);

  if (question.status === "retired") {
    return canAuthor ? (
      <Button variant="secondary" icon="refresh" onClick={() => run(() => restore(question.question_id).unwrap(), "Question restored")}>
        Restore
      </Button>
    ) : null;
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {canAuthor && (!working || working.status === "draft") && (
        <Button variant="secondary" icon="edit" onClick={() => navigate(`/questions/${question.question_id}/edit`)}>
          Edit
        </Button>
      )}
      {canAuthor && working?.status === "draft" && (
        <>
          <Button
            icon="upload"
            loading={submitting}
            onClick={() =>
              confirm.ask(
                { title: "Submit for review?", description: "Another reviewer must approve it before it publishes.", confirmLabel: "Submit", tone: "primary" },
                () => run(() => submit(question.question_id).unwrap(), "Submitted for review"),
              )
            }
          >
            Submit for review
          </Button>
          {question.current && (
            <Button
              variant="secondary"
              icon="trash"
              onClick={() =>
                confirm.ask({ title: "Discard this draft?", description: "Reverts to the published version. This cannot be undone.", confirmLabel: "Discard" }, () =>
                  run(() => deleteDraft(question.question_id).unwrap(), "Draft discarded"),
                )
              }
            >
              Discard draft
            </Button>
          )}
        </>
      )}
      {canReviewThis && working?.status === "in_review" && (
        <>
          <Button
            icon="check"
            loading={approving}
            onClick={() =>
              confirm.ask(
                { title: "Approve and publish?", description: "It becomes the live version students may see on a test.", confirmLabel: "Approve", tone: "primary" },
                () => run(() => approve({ questionId: question.question_id }).unwrap(), "Question published"),
              )
            }
          >
            Approve
          </Button>
          <Button variant="secondary" icon="x" onClick={() => setRejecting(true)}>
            Reject
          </Button>
        </>
      )}
      {canAuthor && question.current && (
        <Button
          variant="secondary"
          icon="ban"
          onClick={() =>
            confirm.ask({ title: "Retire this question?", description: "Refused while a published test still uses it.", confirmLabel: "Retire" }, () =>
              run(() => retire(question.question_id).unwrap(), "Question retired"),
            )
          }
        >
          Retire
        </Button>
      )}
      <ConfirmDialog {...confirm.dialogProps} />
      {rejecting && <RejectQuestionDialog open={rejecting} onClose={() => setRejecting(false)} questionId={question.question_id} />}
    </div>
  );
}
