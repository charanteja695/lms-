import { FormProvider, useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useApproveCourseRequestMutation } from "@/modules/subscriptions/course-requests/api/courseRequestsApi";
import type { CourseRequest } from "@/modules/subscriptions/course-requests/types";
import { TextField } from "@/shared/form";
import { Button, Modal } from "@/shared/ui";

interface ApproveFormValues {
  seats: string;
  term_days: string;
}

export function ApproveDialog({ open, onClose, request }: { open: boolean; onClose: () => void; request: CourseRequest }) {
  const notify = useNotify();
  const navigate = useNavigate();
  const [approve, { isLoading }] = useApproveCourseRequestMutation();
  const form = useForm<ApproveFormValues>({ defaultValues: { seats: String(request.requested_seats), term_days: String(request.requested_term_days) } });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Approve this request?"
      description="Creates an active subscription. You may grant a different seat count or term than requested."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button type="submit" form="approve-form" loading={isLoading}>
            Approve
          </Button>
        </>
      }
    >
      <FormProvider {...form}>
        <form
          id="approve-form"
          noValidate
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={form.handleSubmit(async (values) => {
            try {
              const seats = Number(values.seats);
              const termDays = Number(values.term_days);
              const subscription = await approve({
                id: request.course_request_id,
                body: {
                  seats: seats === request.requested_seats ? null : seats,
                  term_days: termDays === request.requested_term_days ? null : termDays,
                },
              }).unwrap();
              notify.success("Course request approved", "The subscription is now active.");
              onClose();
              navigate(`/subscriptions/${subscription.subscription_id}`);
            } catch (error) {
              notify.apiError(error);
            }
          })}
        >
          <TextField<ApproveFormValues> name="seats" label="Seats" type="number" required />
          <TextField<ApproveFormValues> name="term_days" label="Term (days)" type="number" required />
        </form>
      </FormProvider>
    </Modal>
  );
}
