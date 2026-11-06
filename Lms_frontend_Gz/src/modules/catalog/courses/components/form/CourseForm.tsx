import { useEffect } from "react";
import { FormProvider, useForm, type UseFormReturn } from "react-hook-form";

import type { CourseFormValues } from "@/modules/catalog/courses/form/courseForm";
import { FormSection, TextareaField, TextField, FormActions } from "@/shared/form";
import { Alert, Button, Card, Icon } from "@/shared/ui";

function toSlug(title: string): string {
  return title
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, "")
    .replace(/[\s_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function CourseForm({
  mode,
  defaultValues,
  submitting,
  formError,
  onSubmit,
  onCancel,
}: {
  mode: "create" | "edit";
  defaultValues: CourseFormValues;
  submitting: boolean;
  formError?: string | null;
  onSubmit: (values: CourseFormValues, form: UseFormReturn<CourseFormValues>) => Promise<void>;
  onCancel: () => void;
}) {
  const form = useForm<CourseFormValues>({ defaultValues, mode: "onTouched" });
  const title = form.watch("title");
  const slug = form.watch("slug");

  // Auto-generate slug from title in create mode if user hasn't explicitly customized it
  useEffect(() => {
    if (mode === "create" && title && !form.formState.dirtyFields.slug) {
      form.setValue("slug", toSlug(title), { shouldValidate: true });
    }
  }, [title, mode, form]);

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
          <FormSection
            title="Course Information"
            description="The title and summary describe the course. The slug serves as the permanent web identifier."
          >
            <TextField<CourseFormValues>
              name="title"
              label="Course Title"
              required
              maxLength={200}
              placeholder="e.g. Modern Full-Stack Web Development"
              className="sm:col-span-2"
            />

            <div className="sm:col-span-2 space-y-1">
              {mode === "create" ? (
                <TextField<CourseFormValues>
                  name="slug"
                  label="URL Slug"
                  required
                  placeholder="modern-full-stack-web-development"
                  hint="Permanent identifier. Auto-generated from title, or enter a custom slug."
                />
              ) : (
                <TextField<CourseFormValues>
                  name="slug"
                  label="URL Slug"
                  disabled
                  hint="Slugs cannot be changed after creation to preserve links."
                />
              )}

              {slug && (
                <p className="flex items-center gap-1 font-mono text-xs text-brand-700 bg-brand-50/60 rounded-lg px-2.5 py-1.5 border border-brand-100">
                  <Icon name="map" size={13} />
                  <span>Public URL: /courses/{slug}</span>
                </p>
              )}
            </div>

            <TextareaField<CourseFormValues>
              name="summary"
              label="Course Summary"
              required
              rows={4}
              maxLength={500}
              hint="Describe what learners will achieve, skills covered, and target outcomes."
              className="sm:col-span-2"
            />

          </FormSection>
        </Card>

        <FormActions>
          <Button variant="secondary" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" loading={submitting}>
            {mode === "create" ? "Create course & start builder" : "Save changes"}
          </Button>
        </FormActions>
      </form>
    </FormProvider>
  );
}
