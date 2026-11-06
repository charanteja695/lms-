import { FormProvider, useForm } from "react-hook-form";

import { useNotify } from "@/core/hooks/useNotify";
import { useDecideCaseMutation } from "@/modules/proctoring/cases/api/casesApi";
import { SelectField, TextareaField } from "@/shared/form";
import { Button, Modal } from "@/shared/ui";

interface DecideFormValues {
  decision: "reviewed_ok" | "invalidated";
  note: string;
}

const DECISION_OPTIONS = [
  { value: "reviewed_ok", label: "Reviewed OK — the attempt stands" },
  { value: "invalidated", label: "Invalidated — the attempt does not stand" },
];

export function DecideCaseDialog({ open, onClose, caseId }: { open: boolean; onClose: () => void; caseId: string }) {
  const notify = useNotify();
  const [decide, { isLoading }] = useDecideCaseMutation();
  const form = useForm<DecideFormValues>({ defaultValues: { decision: "reviewed_ok", note: "" } });
  const decision = form.watch("decision");

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Decide this case"
      description="Nothing here invalidates an attempt automatically — this is your call."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button type="submit" form="decide-case-form" variant={decision === "invalidated" ? "danger" : "primary"} loading={isLoading}>
            Submit decision
          </Button>
        </>
      }
    >
      <FormProvider {...form}>
        <form
          id="decide-case-form"
          noValidate
          className="space-y-4"
          onSubmit={form.handleSubmit(async (values) => {
            try {
              await decide({ caseId, decision: values.decision, note: values.note || undefined }).unwrap();
              notify.success("Decision recorded");
              onClose();
            } catch (error) {
              notify.apiError(error);
            }
          })}
        >
          <SelectField<DecideFormValues> name="decision" label="Decision" options={DECISION_OPTIONS} required />
          <TextareaField<DecideFormValues>
            name="note"
            label="Note"
            rows={4}
            maxLength={2000}
            required={decision === "invalidated"}
            hint={decision === "invalidated" ? "A written reason of at least 10 characters is required to invalidate an attempt." : "Optional."}
          />
        </form>
      </FormProvider>
    </Modal>
  );
}
