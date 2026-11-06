import { FormProvider, useForm } from "react-hook-form";

import { useNotify } from "@/core/hooks/useNotify";
import { useWarnSessionMutation } from "@/modules/proctoring/monitor/api/monitorApi";
import { TextareaField } from "@/shared/form";
import { Button, Modal } from "@/shared/ui";

interface WarnFormValues {
  message: string;
}

export function WarnSessionDialog({ open, onClose, sessionId }: { open: boolean; onClose: () => void; sessionId: string }) {
  const notify = useNotify();
  const [warn, { isLoading }] = useWarnSessionMutation();
  const form = useForm<WarnFormValues>({ defaultValues: { message: "" } });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Warn this student"
      description="Delivered with their next heartbeat."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button type="submit" form="warn-session-form" loading={isLoading}>
            Send warning
          </Button>
        </>
      }
    >
      <FormProvider {...form}>
        <form
          id="warn-session-form"
          noValidate
          onSubmit={form.handleSubmit(async (values) => {
            try {
              await warn({ sessionId, message: values.message }).unwrap();
              notify.success("Warning sent");
              onClose();
            } catch (error) {
              notify.apiError(error);
            }
          })}
        >
          <TextareaField<WarnFormValues> name="message" label="Message" required rows={3} maxLength={500} rules={{ required: "A message is required." }} />
        </form>
      </FormProvider>
    </Modal>
  );
}
