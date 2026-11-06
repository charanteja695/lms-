import { useNavigate } from "react-router-dom";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { useDeleteProblemMutation, usePublishProblemMutation, useRetireProblemMutation } from "@/modules/code-execution/problems/api/problemsApi";
import type { ProblemAuthor } from "@/modules/code-execution/problems/types";
import { Button, ConfirmDialog, Menu } from "@/shared/ui";

export function ProblemLifecycleActions({ problem }: { problem: ProblemAuthor }) {
  const navigate = useNavigate();
  const notify = useNotify();
  const confirm = useConfirmAction();
  const [publish, { isLoading: publishing }] = usePublishProblemMutation();
  const [retire] = useRetireProblemMutation();
  const [deleteProblem] = useDeleteProblemMutation();

  const run = async (work: () => Promise<unknown>, success: string) => {
    try {
      await work();
      notify.success(success);
    } catch (error) {
      notify.apiError(error);
    }
  };

  if (problem.status === "draft") {
    return (
      <>
        <Button variant="secondary" icon="edit" onClick={() => navigate(`/problems/${problem.problem_id}/edit`)}>
          Edit
        </Button>
        <Button
          icon="upload"
          loading={publishing}
          onClick={() =>
            confirm.ask(
              { title: "Publish this problem?", description: "Students can see and attempt it. It becomes frozen — no further edits.", confirmLabel: "Publish", tone: "primary" },
              () => run(() => publish(problem.problem_id).unwrap(), "Problem published"),
            )
          }
        >
          Publish
        </Button>
        <Menu
          trigger={<Button variant="secondary" icon="more">More</Button>}
          items={[
            {
              label: "Delete",
              icon: "trash",
              tone: "danger",
              onSelect: () =>
                confirm.ask({ title: "Delete this problem?", description: "This cannot be undone.", confirmLabel: "Delete" }, async () => {
                  await run(() => deleteProblem(problem.problem_id).unwrap(), "Problem deleted");
                  navigate("/problems", { replace: true });
                }),
            },
          ]}
        />
        <ConfirmDialog {...confirm.dialogProps} />
      </>
    );
  }

  if (problem.status === "published") {
    return (
      <>
        <Button
          variant="secondary"
          icon="archive"
          onClick={() =>
            confirm.ask(
              { title: "Retire this problem?", description: "Students can no longer attempt it. This cannot be undone.", confirmLabel: "Retire" },
              () => run(() => retire(problem.problem_id).unwrap(), "Problem retired"),
            )
          }
        >
          Retire
        </Button>
        <ConfirmDialog {...confirm.dialogProps} />
      </>
    );
  }

  return null;
}
