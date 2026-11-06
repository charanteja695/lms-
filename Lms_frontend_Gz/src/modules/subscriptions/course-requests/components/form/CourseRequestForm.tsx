import { FormProvider, useForm, type UseFormReturn } from "react-hook-form";

import { CourseField } from "@/modules/subscriptions/course-requests/components/form/CourseField";
import type { CourseRequestFormValues } from "@/modules/subscriptions/course-requests/form/courseRequestForm";
import { FormSection, TextField, FormActions } from "@/shared/form";
import { Alert, Button, Card } from "@/shared/ui";

export function CourseRequestForm({ defaultValues, submitting, formError, onSubmit, onCancel }: {
  defaultValues: CourseRequestFormValues;
  submitting: boolean;
  formError?: string | null;
  onSubmit: (values: CourseRequestFormValues, form: UseFormReturn<CourseRequestFormValues>) => Promise<void>;
  onCancel: () => void;
}) {
  const form = useForm<CourseRequestFormValues>({ defaultValues, mode: "onTouched" });

  return (
    <FormProvider {...form}>
      <form
        noValidate
        className="space-y-6"
        onSubmit={form.handleSubmit(async (values) => {
          await onSubmit(values, form);
        })}
      >
        {formError && <Alert tone="error">{formError}</Alert>}
        <Card>
          <FormSection title="Course request" description="For your own institution. An admin reviews and approves it.">
            <div className="sm:col-span-2">
              <CourseField />
            </div>
            <TextField<CourseRequestFormValues> name="requested_seats" label="Seats" type="number" required hint="Up to 100,000." />
            <TextField<CourseRequestFormValues> name="requested_term_days" label="Term (days)" type="number" required hint="Up to 3,650 (10 years)." />
          </FormSection>
        </Card>
        <FormActions>
          <Button variant="secondary" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" loading={submitting}>
            Submit request
          </Button>
        </FormActions>
      </form>
    </FormProvider>
  );
}
