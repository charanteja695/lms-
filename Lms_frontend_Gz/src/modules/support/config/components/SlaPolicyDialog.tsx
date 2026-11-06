import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { PRIORITY_LABELS, QUEUE_LABELS } from "@/modules/support/common/labels";
import { useResetSlaPolicyMutation, useSaveSlaPolicyMutation, type SlaPolicy } from "@/modules/support/config/api/slaPoliciesApi";
import { Button, Field, Input, Modal } from "@/shared/ui";

/** Targets are in minutes; the server checks resolution ≥ first response (INVALID_SLA_TARGETS). */
export function SlaPolicyDialog({ policy, onClose }: { policy: SlaPolicy; onClose: () => void }) {
  const notify = useNotify();
  const [first, setFirst] = useState(String(policy.first_response_minutes));
  const [resolution, setResolution] = useState(String(policy.resolution_minutes));
  const [save, { isLoading: saving }] = useSaveSlaPolicyMutation();
  const [reset, { isLoading: resetting }] = useResetSlaPolicyMutation();

  const run = async (work: () => Promise<unknown>, message: string) => {
    try {
      await work();
      notify.success(message);
      onClose();
    } catch (error) {
      notify.apiError(error);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={`${QUEUE_LABELS[policy.queue]} · ${PRIORITY_LABELS[policy.priority]}`}
      description="Applies to tickets created or re-prioritised from now on."
      footer={
        <>
          {!policy.is_default && (
            <Button variant="ghost" loading={resetting} onClick={() => void run(() => reset({ queue: policy.queue, priority: policy.priority }).unwrap(), "Back to the default")}>
              Reset to default
            </Button>
          )}
          <span className="flex-1" />
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            loading={saving}
            onClick={() =>
              void run(
                () => save({ queue: policy.queue, priority: policy.priority, first_response_minutes: Number(first), resolution_minutes: Number(resolution) }).unwrap(),
                "SLA policy saved",
              )
            }
          >
            Save
          </Button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="First response (minutes)" required>{(props) => <Input {...props} type="number" min={1} value={first} onChange={(event) => setFirst(event.target.value)} />}</Field>
        <Field label="Resolution (minutes)" required>{(props) => <Input {...props} type="number" min={1} value={resolution} onChange={(event) => setResolution(event.target.value)} />}</Field>
      </div>
    </Modal>
  );
}
