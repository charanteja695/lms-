import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { useApproveTestMutation, useCloneTestMutation, useDeleteTestMutation, useRetireTestMutation, useSubmitTestMutation } from "@/modules/assessments/tests/api/testsApi";
import { RejectTestDialog } from "@/modules/assessments/tests/components/detail/RejectTestDialog";
import type { Test } from "@/modules/assessments/tests/types";
import { Button, ConfirmDialog, Menu } from "@/shared/ui";

export function TestLifecycleActions({ test, canAuthor, canReview }: { test: Test; canAuthor: boolean; canReview: boolean }) {
  const navigate = useNavigate();
  const notify = useNotify();
  const confirm = useConfirmAction();
  const [submit, { isLoading: submitting }] = useSubmitTestMutation();
  const [approve, { isLoading: approving }] = useApproveTestMutation();
  const [retire] = useRetireTestMutation();
  const [clone, { isLoading: cloning }] = useCloneTestMutation();
  const [deleteTest] = useDeleteTestMutation();
  const [rejecting, setRejecting] = useState(false);

  const run = async (work: () => Promise<unknown>, success: string) => {
    try {
      await work();
      notify.success(success);
    } catch (error) {
      notify.apiError(error);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      {canAuthor && test.status === "draft" && (
        <>
          <Button variant="secondary" icon="edit" onClick={() => navigate(`/tests/${test.test_id}/edit`)}>
            Edit
          </Button>
          <Button
            icon="upload"
            loading={submitting}
            onClick={() =>
              confirm.ask(
                { title: "Submit for review?", description: "A reviewer must approve it before it publishes.", confirmLabel: "Submit", tone: "primary" },
                () => run(() => submit(test.test_id).unwrap(), "Submitted for review"),
              )
            }
          >
            Submit for review
          </Button>
        </>
      )}
      {canReview && test.status === "in_review" && (
        <>
          <Button
            icon="check"
            loading={approving}
            onClick={() =>
              confirm.ask(
                { title: "Approve and publish?", description: "This freezes the total marks and question count. No further edits.", confirmLabel: "Approve", tone: "primary" },
                () => run(() => approve({ testId: test.test_id }).unwrap(), "Test published"),
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
      {canReview && test.status === "published" && (
        <Button
          variant="secondary"
          icon="archive"
          onClick={() =>
            confirm.ask({ title: "Retire this test?", description: "Students can no longer start new attempts.", confirmLabel: "Retire" }, () =>
              run(() => retire(test.test_id).unwrap(), "Test retired"),
            )
          }
        >
          Retire
        </Button>
      )}
      {canAuthor && (test.status === "published" || test.status === "retired") && (
        <Button
          variant="secondary"
          icon="refresh"
          loading={cloning}
          onClick={() =>
            confirm.ask({ title: "Clone this test?", description: "Starts a new draft with the same settings and sections.", confirmLabel: "Clone", tone: "primary" }, async () => {
              const cloned = await clone(test.test_id).unwrap();
              notify.success("Draft created from clone");
              navigate(`/tests/${cloned.test_id}`);
            })
          }
        >
          Clone
        </Button>
      )}
      {canAuthor && test.status === "draft" && (
        <Menu
          trigger={<Button variant="secondary" icon="more">More</Button>}
          items={[
            {
              label: "Delete",
              icon: "trash",
              tone: "danger",
              onSelect: () =>
                confirm.ask({ title: "Delete this test?", description: "This cannot be undone.", confirmLabel: "Delete" }, async () => {
                  await run(() => deleteTest(test.test_id).unwrap(), "Test deleted");
                  navigate("/tests", { replace: true });
                }),
            },
          ]}
        />
      )}
      <ConfirmDialog {...confirm.dialogProps} />
      {rejecting && <RejectTestDialog open={rejecting} onClose={() => setRejecting(false)} testId={test.test_id} />}
    </div>
  );
}
