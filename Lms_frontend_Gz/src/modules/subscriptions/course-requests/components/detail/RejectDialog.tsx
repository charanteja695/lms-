import { FormProvider, useForm } from "react-hook-form";

import { useNotify } from "@/core/hooks/useNotify";
import { useRejectCourseRequestMutation } from "@/modules/subscriptions/course-requests/api/courseRequestsApi";
import { TextareaField } from "@/shared/form";
import { Button, Modal } from "@/shared/ui";

interface RejectFormValues {
  reason: string;
}

export function RejectDialog({ open, onClose, courseRequestId }: { open: boolean; onClose: () => void; courseRequestId: string }) {
  const notify = useNotify();
  const [reject, { isLoading }] = useRejectCourseRequestMutation();
  const form = useForm<RejectFormValues>({ defaultValues: { reason: "" } });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Reject this request?"
      description="The institution can see why and submit a new request."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button type="submit" form="reject-course-request-form" variant="danger" loading={isLoading}>
            Reject
          </Button>
        </>
      }
    >
      <FormProvider {...form}>
        <form
          id="reject-course-request-form"
          noValidate
          onSubmit={form.handleSubmit(async (values) => {
            try {
              await reject({ id: courseRequestId, reason: values.reason }).unwrap();
              notify.success("Course request rejected");
              onClose();
            } catch (error) {
              notify.apiError(error);
            }
          })}
        >
          <TextareaField<RejectFormValues>
            name="reason"
            label="Reason"
            required
            rows={4}
            maxLength={500}
            rules={{ required: "Tell the institution why.", minLength: { value: 3, message: "At least 3 characters." } }}
          />
        </form>
      </FormProvider>
    </Modal>
  );
}
