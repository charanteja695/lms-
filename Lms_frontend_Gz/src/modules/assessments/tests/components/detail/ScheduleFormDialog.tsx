import { FormProvider, useForm } from "react-hook-form";

import { useNotify } from "@/core/hooks/useNotify";
import { useCreateScheduleMutation } from "@/modules/assessments/tests/api/testsApi";
import { CheckboxField, TextField } from "@/shared/form";
import { Button, Modal } from "@/shared/ui";

interface ScheduleFormValues {
  title: string;
  starts_at: string;
  ends_at: string;
  enforce_end: boolean;
  results_release_at: string;
}

export function ScheduleFormDialog({ open, onClose, testId }: { open: boolean; onClose: () => void; testId: string }) {
  const notify = useNotify();
  const [createSchedule, { isLoading }] = useCreateScheduleMutation();
  const form = useForm<ScheduleFormValues>({ defaultValues: { title: "", starts_at: "", ends_at: "", enforce_end: true, results_release_at: "" } });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New exam window"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button type="submit" form="schedule-form" loading={isLoading}>
            Create
          </Button>
        </>
      }
    >
      <FormProvider {...form}>
        <form
          id="schedule-form"
          noValidate
          className="space-y-4"
          onSubmit={form.handleSubmit(async (values) => {
            try {
              await createSchedule({
                testId,
                body: {
                  title: values.title || null,
                  starts_at: new Date(values.starts_at).toISOString(),
                  ends_at: new Date(values.ends_at).toISOString(),
                  enforce_end: values.enforce_end,
                  results_release_at: values.results_release_at ? new Date(values.results_release_at).toISOString() : null,
                },
              }).unwrap();
              notify.success("Exam window scheduled");
              onClose();
            } catch (error) {
              notify.apiError(error);
            }
          })}
        >
          <TextField<ScheduleFormValues> name="title" label="Title" hint="Optional, e.g. a batch name." />
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField<ScheduleFormValues> name="starts_at" label="Opens" type="date" required />
            <TextField<ScheduleFormValues> name="ends_at" label="Closes" type="date" required />
          </div>
          <TextField<ScheduleFormValues> name="results_release_at" label="Release results at" type="date" hint="Optional, for 'when the exam window closes' result visibility." />
          <CheckboxField<ScheduleFormValues> name="enforce_end" label="Cut off a late starter at the window's end" />
        </form>
      </FormProvider>
    </Modal>
  );
}
