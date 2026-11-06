import { useState } from "react";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { usePauseSessionMutation, useResumeSessionMutation, useTerminateSessionMutation } from "@/modules/proctoring/monitor/api/monitorApi";
import { WarnSessionDialog } from "@/modules/proctoring/monitor/components/detail/WarnSessionDialog";
import type { SessionStatus } from "@/modules/proctoring/common/types";
import { Button, ConfirmDialog } from "@/shared/ui";

export function SessionControls({ sessionId, status }: { sessionId: string; status: SessionStatus }) {
  const notify = useNotify();
  const confirm = useConfirmAction();
  const [warning, setWarning] = useState(false);
  const [pause, { isLoading: pausing }] = usePauseSessionMutation();
  const [resume, { isLoading: resuming }] = useResumeSessionMutation();
  const [terminate] = useTerminateSessionMutation();

  const run = async (work: () => Promise<unknown>, success: string) => {
    try {
      await work();
      notify.success(success);
    } catch (error) {
      notify.apiError(error);
    }
  };

  if (status !== "ready" && status !== "active") return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button variant="secondary" icon="alert" onClick={() => setWarning(true)}>
        Warn
      </Button>
      <Button
        variant="secondary"
        icon="clock"
        loading={pausing}
        onClick={() =>
          confirm.ask({ title: "Pause this attempt?", description: "Acts on the attempt in assessment-service; the stopped time is given back on resume.", confirmLabel: "Pause", withReason: true }, (reason) =>
            run(() => pause({ sessionId, message: reason }).unwrap(), "Attempt paused"),
          )
        }
      >
        Pause
      </Button>
      <Button icon="play" loading={resuming} onClick={() => run(() => resume(sessionId).unwrap(), "Attempt resumed")}>
        Resume
      </Button>
      <Button
        variant="danger"
        icon="ban"
        onClick={() =>
          confirm.ask(
            { title: "Terminate this attempt?", description: "It is submitted immediately. A person then reviews the integrity case.", confirmLabel: "Terminate", withReason: true },
            (reason) => run(() => terminate({ sessionId, message: reason }).unwrap(), "Attempt terminated"),
          )
        }
      >
        Terminate
      </Button>
      <ConfirmDialog {...confirm.dialogProps} />
      <WarnSessionDialog open={warning} onClose={() => setWarning(false)} sessionId={sessionId} />
    </div>
  );
}
