import { FormProvider, useForm, type UseFormReturn } from "react-hook-form";

import { CourseField } from "@/modules/learning/batches/components/form/CourseField";
import { InstitutionField } from "@/modules/learning/batches/components/form/InstitutionField";
import type { BatchFormValues } from "@/modules/learning/batches/form/batchForm";
import { FormSection, TextField, FormActions } from "@/shared/form";
import { Alert, Button, Card } from "@/shared/ui";

export function BatchForm({ defaultValues, showInstitutionField, submitting, formError, onSubmit, onCancel }: {
  defaultValues: BatchFormValues;
  /** Only accounts.manage admins pick the institution; an institution head's own is used automatically. */
  showInstitutionField: boolean;
  submitting: boolean;
  formError?: string | null;
  onSubmit: (values: BatchFormValues, form: UseFormReturn<BatchFormValues>) => Promise<void>;
  onCancel: () => void;
}) {
  const form = useForm<BatchFormValues>({ defaultValues, mode: "onTouched" });

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
          <FormSection title="Batch" description="A group of students taking one course version together.">
            {showInstitutionField && (
              <div className="sm:col-span-2">
                <InstitutionField />
              </div>
            )}
            <div className="sm:col-span-2">
              <CourseField />
            </div>
            <TextField<BatchFormValues> name="name" label="Batch name" required maxLength={200} placeholder="2026 Batch A" className="sm:col-span-2" />
          </FormSection>
        </Card>
        <FormActions>
          <Button variant="secondary" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" loading={submitting}>
            Create batch
          </Button>
        </FormActions>
      </form>
    </FormProvider>
  );
}
