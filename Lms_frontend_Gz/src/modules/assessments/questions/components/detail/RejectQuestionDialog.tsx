import { FormProvider, useForm } from "react-hook-form";

import { useNotify } from "@/core/hooks/useNotify";
import { useRejectQuestionMutation } from "@/modules/assessments/questions/api/questionsApi";
import { TextareaField } from "@/shared/form";
import { Button, Modal } from "@/shared/ui";

interface RejectFormValues {
  note: string;
}

export function RejectQuestionDialog({ open, onClose, questionId }: { open: boolean; onClose: () => void; questionId: string }) {
  const notify = useNotify();
  const [reject, { isLoading }] = useRejectQuestionMutation();
  const form = useForm<RejectFormValues>({ defaultValues: { note: "" } });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Reject this question?"
      description="It goes back to draft so the author can fix it."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button type="submit" form="reject-question-form" variant="danger" loading={isLoading}>
            Reject
          </Button>
        </>
      }
    >
      <FormProvider {...form}>
        <form
          id="reject-question-form"
          noValidate
          onSubmit={form.handleSubmit(async (values) => {
            try {
              await reject({ questionId, note: values.note }).unwrap();
              notify.success("Sent back to draft");
              onClose();
            } catch (error) {
              notify.apiError(error);
            }
          })}
        >
          <TextareaField<RejectFormValues> name="note" label="Note" required rows={4} maxLength={500} rules={{ required: "Tell the author what to fix.", minLength: { value: 1, message: "Required." } }} />
        </form>
      </FormProvider>
    </Modal>
  );
}
