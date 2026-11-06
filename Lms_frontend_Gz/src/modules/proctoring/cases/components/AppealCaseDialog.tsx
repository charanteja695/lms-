import { FormProvider, useForm } from "react-hook-form";

import { useNotify } from "@/core/hooks/useNotify";
import { useAppealCaseMutation } from "@/modules/proctoring/cases/api/casesApi";
import { TextareaField } from "@/shared/form";
import { Button, Modal } from "@/shared/ui";

interface AppealFormValues {
  reason: string;
}

export function AppealCaseDialog({ open, onClose, caseId }: { open: boolean; onClose: () => void; caseId: string }) {
  const notify = useNotify();
  const [appeal, { isLoading }] = useAppealCaseMutation();
  const form = useForm<AppealFormValues>({ defaultValues: { reason: "" } });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Appeal this decision"
      description="You may appeal an invalidation once. A different exam manager than the one who decided will review it."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button type="submit" form="appeal-case-form" loading={isLoading}>
            Submit appeal
          </Button>
        </>
      }
    >
      <FormProvider {...form}>
        <form
          id="appeal-case-form"
          noValidate
          onSubmit={form.handleSubmit(async (values) => {
            try {
              await appeal({ caseId, reason: values.reason }).unwrap();
              notify.success("Appeal submitted");
              onClose();
            } catch (error) {
              notify.apiError(error);
            }
          })}
        >
          <TextareaField<AppealFormValues> name="reason" label="Why should this decision be reconsidered?" required rows={5} maxLength={2000} />
        </form>
      </FormProvider>
    </Modal>
  );
}
