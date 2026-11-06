import { useEffect, useState, type ReactNode } from "react";

import { Button } from "./Button";
import { Field } from "./Field";
import { Modal } from "./Modal";
import { Textarea } from "./Textarea";

export interface ConfirmOptions {
  title: string;
  description: ReactNode;
  confirmLabel: string;
  tone?: "danger" | "primary";
  /** Ask for an optional reason (e.g. when suspending). */
  withReason?: boolean;
}

export function ConfirmDialog({ open, options, loading, onConfirm, onCancel }: {
  open: boolean;
  options: ConfirmOptions | null;
  loading?: boolean;
  onConfirm: (reason?: string) => void;
  onCancel: () => void;
}) {
  const [reason, setReason] = useState("");
  useEffect(() => {
    if (open) setReason("");
  }, [open]);
  if (!options) return null;
  return (
    <Modal
      open={open}
      onClose={loading ? () => undefined : onCancel}
      title={options.title}
      description={options.description}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onCancel} disabled={loading}>
            Cancel
          </Button>
          <Button variant={options.tone === "primary" ? "primary" : "danger"} loading={loading} onClick={() => onConfirm(reason.trim() || undefined)}>
            {options.confirmLabel}
          </Button>
        </>
      }
    >
      {options.withReason && (
        <Field label="Reason" hint="Optional. Visible to administrators.">
          {(props) => <Textarea {...props} value={reason} maxLength={500} onChange={(event) => setReason(event.target.value)} />}
        </Field>
      )}
    </Modal>
  );
}
