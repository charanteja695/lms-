import { FormProvider, useForm, type UseFormReturn } from "react-hook-form";

import { TEMPLATE_PLACEHOLDERS } from "@/modules/certificates/common/labels";
import { GradeBandsEditor } from "@/modules/certificates/templates/components/form/GradeBandsEditor";
import { SignatoriesEditor } from "@/modules/certificates/templates/components/form/SignatoriesEditor";
import { TemplateCourseField } from "@/modules/certificates/templates/components/form/TemplateCourseField";
import type { TemplateFormValues } from "@/modules/certificates/templates/form/templateForm";
import { FormSection, TextareaField, TextField, FormActions } from "@/shared/form";
import { Alert, Button, Card } from "@/shared/ui";

const PLACEHOLDER_HINT = `Placeholders: ${TEMPLATE_PLACEHOLDERS.join(" ")}`;

export function TemplateForm({ defaultValues, isEdit, submitting, formError, onSubmit, onCancel }: {
  defaultValues: TemplateFormValues;
  isEdit: boolean;
  submitting: boolean;
  formError?: string | null;
  onSubmit: (values: TemplateFormValues, form: UseFormReturn<TemplateFormValues>) => Promise<void>;
  onCancel: () => void;
}) {
  const form = useForm<TemplateFormValues>({ defaultValues, mode: "onTouched" });

  return (
    <FormProvider {...form}>
      <form noValidate className="space-y-6" onSubmit={form.handleSubmit((values) => onSubmit(values, form))}>
        {formError && <Alert tone="error">{formError}</Alert>}
        <Card>
          <FormSection title="Template" description="Which course it applies to, and its name in this list.">
            <TextField<TemplateFormValues> name="name" label="Name" required maxLength={120} className="sm:col-span-2" />
            <div className="sm:col-span-2">
              <TemplateCourseField disabled={isEdit} />
            </div>
          </FormSection>
          <FormSection title="Wording" description="What the certificate says. The certificate keeps a copy; later edits never change one already issued.">
            <TextField<TemplateFormValues> name="title_text" label="Title" required maxLength={120} className="sm:col-span-2" />
            <TextareaField<TemplateFormValues> name="body_text" label="Body" hint={PLACEHOLDER_HINT} rows={4} maxLength={1000} className="sm:col-span-2" />
            <TextareaField<TemplateFormValues> name="footer_text" label="Footer" hint={PLACEHOLDER_HINT} rows={2} maxLength={300} className="sm:col-span-2" />
            <TextField<TemplateFormValues> name="accent_color" label="Accent colour" hint="A hex colour such as #00663C. Leave empty for the platform's brand colour." maxLength={7} />
          </FormSection>
          <FormSection title="Signatories" description="Up to three people who sign the certificate.">
            <SignatoriesEditor />
          </FormSection>
          <FormSection title="Grade bands" description="Map a score to a label. The lowest band must start at 0.">
            <GradeBandsEditor />
          </FormSection>
        </Card>
        <FormActions>
          <Button variant="secondary" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" loading={submitting}>
            {isEdit ? "Save" : "Create draft"}
          </Button>
        </FormActions>
      </form>
    </FormProvider>
  );
}
