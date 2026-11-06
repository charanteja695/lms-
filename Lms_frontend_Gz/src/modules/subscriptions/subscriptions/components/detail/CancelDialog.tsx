import { FormProvider, useForm } from "react-hook-form";

import { useNotify } from "@/core/hooks/useNotify";
import { useCancelSubscriptionMutation } from "@/modules/subscriptions/subscriptions/api/subscriptionsApi";
import { TextareaField } from "@/shared/form";
import { Button, Modal } from "@/shared/ui";

interface CancelFormValues {
  reason: string;
}

export function CancelDialog({ open, onClose, subscriptionId }: { open: boolean; onClose: () => void; subscriptionId: string }) {
  const notify = useNotify();
  const [cancel, { isLoading }] = useCancelSubscriptionMutation();
  const form = useForm<CancelFormValues>({ defaultValues: { reason: "" } });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Cancel this subscription?"
      description="Seats stop being available to the institution immediately. This cannot be undone."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Keep subscription
          </Button>
          <Button type="submit" form="cancel-subscription-form" variant="danger" loading={isLoading}>
            Cancel subscription
          </Button>
        </>
      }
    >
      <FormProvider {...form}>
        <form
          id="cancel-subscription-form"
          noValidate
          onSubmit={form.handleSubmit(async (values) => {
            try {
              await cancel({ id: subscriptionId, reason: values.reason }).unwrap();
              notify.success("Subscription cancelled");
              onClose();
            } catch (error) {
              notify.apiError(error);
            }
          })}
        >
          <TextareaField<CancelFormValues>
            name="reason"
            label="Reason"
            required
            rows={4}
            maxLength={500}
            rules={{ required: "Say why this is being cancelled.", minLength: { value: 3, message: "At least 3 characters." } }}
          />
        </form>
      </FormProvider>
    </Modal>
  );
}
