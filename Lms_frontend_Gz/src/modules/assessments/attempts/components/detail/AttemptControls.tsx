import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { usePauseAttemptMutation, useRegradeAttemptMutation, useTerminateAttemptMutation, useUnpauseAttemptMutation } from "@/modules/assessments/attempts/api/attemptsApi";
import type { AttemptStatus } from "@/modules/assessments/common/types";
import { Button, ConfirmDialog } from "@/shared/ui";

export function AttemptControls({ attemptId, status }: { attemptId: string; status: AttemptStatus }) {
  const notify = useNotify();
  const confirm = useConfirmAction();
  const [pause, { isLoading: pausing }] = usePauseAttemptMutation();
  const [unpause, { isLoading: unpausing }] = useUnpauseAttemptMutation();
  const [terminate] = useTerminateAttemptMutation();
  const [regrade, { isLoading: regrading }] = useRegradeAttemptMutation();

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
      {status === "in_progress" && (
        <Button
          variant="secondary"
          icon="clock"
          loading={pausing}
          onClick={() =>
            confirm.ask({ title: "Pause this attempt?", description: "The stopped time is given back when it's unpaused.", confirmLabel: "Pause", withReason: true }, (reason) =>
              run(() => pause({ attemptId, reason }).unwrap(), "Attempt paused"),
            )
          }
        >
          Pause
        </Button>
      )}
      {status === "paused" && (
        <Button icon="play" loading={unpausing} onClick={() => run(() => unpause(attemptId).unwrap(), "Attempt resumed")}>
          Unpause
        </Button>
      )}
      {(status === "in_progress" || status === "paused") && (
        <Button
          variant="danger"
          icon="ban"
          onClick={() =>
            confirm.ask({ title: "Terminate this attempt?", description: "It is submitted immediately with whatever was answered so far.", confirmLabel: "Terminate", withReason: true }, (reason) =>
              run(() => terminate({ attemptId, reason }).unwrap(), "Attempt terminated"),
            )
          }
        >
          Terminate
        </Button>
      )}
      {status === "graded" && (
        <Button
          variant="secondary"
          icon="refresh"
          loading={regrading}
          onClick={() =>
            confirm.ask({ title: "Regrade this attempt?", description: "Re-runs objective scoring; any human grades already given are kept.", confirmLabel: "Regrade" }, () =>
              run(() => regrade(attemptId).unwrap(), "Regraded"),
            )
          }
        >
          Regrade
        </Button>
      )}
      <ConfirmDialog {...confirm.dialogProps} />
    </div>
  );
}
