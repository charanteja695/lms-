import { FormProvider, useForm, type UseFormReturn } from "react-hook-form";

import type { LearningPathFormValues } from "@/modules/catalog/learning-paths/form/learningPathForm";
import { FormSection, TextareaField, TextField, FormActions } from "@/shared/form";
import { Alert, Button, Card } from "@/shared/ui";

export function LearningPathForm({ mode, defaultValues, submitting, formError, onSubmit, onCancel }: {
  mode: "create" | "edit";
  defaultValues: LearningPathFormValues;
  submitting: boolean;
  formError?: string | null;
  onSubmit: (values: LearningPathFormValues, form: UseFormReturn<LearningPathFormValues>) => Promise<void>;
  onCancel: () => void;
}) {
  const form = useForm<LearningPathFormValues>({ defaultValues, mode: "onTouched" });

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
          <FormSection title="Learning path" description="The slug is the public URL identifier and cannot change later.">
            <TextField<LearningPathFormValues> name="title" label="Title" required maxLength={200} className="sm:col-span-2" />
            {mode === "create" ? (
              <TextField<LearningPathFormValues> name="slug" label="Slug" required placeholder="full-stack-web-developer" />
            ) : (
              <TextField<LearningPathFormValues> name="slug" label="Slug" disabled hint="Slugs cannot be changed after creation." />
            )}
            <TextareaField<LearningPathFormValues> name="description" label="Description" required rows={4} maxLength={1000} className="sm:col-span-2" />
          </FormSection>
        </Card>
        <FormActions>
          <Button variant="secondary" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" loading={submitting}>
            {mode === "create" ? "Create learning path" : "Save changes"}
          </Button>
        </FormActions>
      </form>
    </FormProvider>
  );
}
