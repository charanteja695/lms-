import { useId, useState } from "react";

import { toApiError } from "@/core/lib/apiError";
import { Alert, Button, Field, Input, Modal } from "@/shared/ui";

/** Add or rename a module, topic or lesson: one title field. The server checks the length and reports problems. */
export function NameDialog({ heading, label, initial = "", submitLabel, placeholder, onSubmit, onClose }: {
  heading: string;
  label: string;
  initial?: string;
  submitLabel: string;
  placeholder?: string;
  onSubmit: (name: string) => Promise<unknown>;
  onClose: () => void;
}) {
  const formId = useId();
  const [name, setName] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await onSubmit(name.trim());
      onClose();
    } catch (caught) {
      const apiError = toApiError(caught);
      setError(apiError.details[0]?.message ?? apiError.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open
      onClose={saving ? () => undefined : onClose}
      size="sm"
      title={heading}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={saving}>Cancel</Button>
          <Button type="submit" form={formId} loading={saving} disabled={!name.trim()}>{submitLabel}</Button>
        </>
      }
    >
      <form id={formId} noValidate onSubmit={(event) => { event.preventDefault(); void save(); }} className="space-y-3">
        {error && <Alert tone="error">{error}</Alert>}
        <Field label={label} required>
          {(props) => <Input {...props} autoFocus value={name} placeholder={placeholder} maxLength={200} onChange={(event) => setName(event.target.value)} />}
        </Field>
      </form>
    </Modal>
  );
}
