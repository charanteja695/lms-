import { FormProvider, useForm } from "react-hook-form";

import { useNotify } from "@/core/hooks/useNotify";
import { useDecideCaseAppealMutation } from "@/modules/proctoring/cases/api/casesApi";
import { SelectField, TextareaField } from "@/shared/form";
import { Button, Modal } from "@/shared/ui";

interface AppealFormValues {
  outcome: "upheld" | "overturned";
  note: string;
}

const OUTCOME_OPTIONS = [
  { value: "upheld", label: "Upheld — the invalidation stands" },
  { value: "overturned", label: "Overturned — the attempt is reviewed OK" },
];

export function DecideAppealDialog({ open, onClose, caseId }: { open: boolean; onClose: () => void; caseId: string }) {
  const notify = useNotify();
  const [decideCaseAppeal, { isLoading }] = useDecideCaseAppealMutation();
  const form = useForm<AppealFormValues>({ defaultValues: { outcome: "upheld", note: "" } });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Decide this appeal"
      description="You were not the first reviewer on this case; that reviewer's decision is final either way until you decide."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button type="submit" form="decide-appeal-form" loading={isLoading}>
            Submit
          </Button>
        </>
      }
    >
      <FormProvider {...form}>
        <form
          id="decide-appeal-form"
          noValidate
          className="space-y-4"
          onSubmit={form.handleSubmit(async (values) => {
            try {
              await decideCaseAppeal({ caseId, outcome: values.outcome, note: values.note }).unwrap();
              notify.success("Appeal decided");
              onClose();
            } catch (error) {
              notify.apiError(error);
            }
          })}
        >
          <SelectField<AppealFormValues> name="outcome" label="Outcome" options={OUTCOME_OPTIONS} required />
          <TextareaField<AppealFormValues> name="note" label="Note" required rows={4} maxLength={2000} />
        </form>
      </FormProvider>
    </Modal>
  );
}
