import { FormProvider, useForm } from "react-hook-form";

import { useNotify } from "@/core/hooks/useNotify";
import { useRejectTestMutation } from "@/modules/assessments/tests/api/testsApi";
import { TextareaField } from "@/shared/form";
import { Button, Modal } from "@/shared/ui";

interface RejectFormValues {
  note: string;
}

export function RejectTestDialog({ open, onClose, testId }: { open: boolean; onClose: () => void; testId: string }) {
  const notify = useNotify();
  const [reject, { isLoading }] = useRejectTestMutation();
  const form = useForm<RejectFormValues>({ defaultValues: { note: "" } });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Reject this test?"
      description="It goes back to draft so the author can fix it."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button type="submit" form="reject-test-form" variant="danger" loading={isLoading}>
            Reject
          </Button>
        </>
      }
    >
      <FormProvider {...form}>
        <form
          id="reject-test-form"
          noValidate
          onSubmit={form.handleSubmit(async (values) => {
            try {
              await reject({ testId, note: values.note }).unwrap();
              notify.success("Sent back to draft");
              onClose();
            } catch (error) {
              notify.apiError(error);
            }
          })}
        >
          <TextareaField<RejectFormValues> name="note" label="Note" required rows={4} maxLength={500} rules={{ required: "Tell the author what to fix." }} />
        </form>
      </FormProvider>
    </Modal>
  );
}
