import { useState } from "react";
import { FormProvider, useForm, type UseFormReturn } from "react-hook-form";

import { toOptions } from "@/core/lib/options";
import { BLOOM_LABELS, QUESTION_TYPE_LABELS } from "@/modules/assessments/common/labels";
import { emptyDraft, type QuestionDraft } from "@/modules/assessments/questions/components/editors/draft";
import { QuestionBodyEditor } from "@/modules/assessments/questions/components/editors/QuestionBodyEditor";
import type { QuestionFormValues } from "@/modules/assessments/questions/form/questionForm";
import { FormSection, SelectField, TextareaField, TextField, FormActions } from "@/shared/form";
import { Alert, Button, Card } from "@/shared/ui";

export function QuestionForm({ mode, defaultValues, defaultDraft, submitting, formError, onSubmit, onCancel }: {
  mode: "create" | "edit";
  defaultValues: QuestionFormValues;
  defaultDraft?: QuestionDraft;
  submitting: boolean;
  formError?: string | null;
  onSubmit: (values: QuestionFormValues, draft: QuestionDraft, form: UseFormReturn<QuestionFormValues>) => Promise<void>;
  onCancel: () => void;
}) {
  const form = useForm<QuestionFormValues>({ defaultValues, mode: "onTouched" });
  const [draft, setDraft] = useState<QuestionDraft>(defaultDraft ?? emptyDraft());
  const type = form.watch("question_type");

  return (
    <FormProvider {...form}>
      <form
        noValidate
        className="space-y-6"
        onSubmit={form.handleSubmit(async (values) => {
          await onSubmit(values, draft, form);
        })}
      >
        {formError && <Alert tone="error">{formError}</Alert>}
        <Card>
          <FormSection title="Question" description="The type cannot change after creation.">
            {mode === "create" ? (
              <SelectField<QuestionFormValues> name="question_type" label="Type" options={toOptions(QUESTION_TYPE_LABELS)} required />
            ) : (
              <TextField<QuestionFormValues> name="question_type" label="Type" disabled />
            )}
            <TextField<QuestionFormValues> name="default_marks" label="Marks" type="number" required />
            <TextareaField<QuestionFormValues> name="text" label="Question text" required rows={4} maxLength={20000} className="sm:col-span-2" />
            <TextareaField<QuestionFormValues> name="explanation" label="Explanation" hint="Shown with the answer, if the test allows it." rows={3} className="sm:col-span-2" />
          </FormSection>
          <FormSection title="Classification">
            <TextField<QuestionFormValues> name="difficulty" label="Difficulty (1–5)" type="number" required />
            <SelectField<QuestionFormValues> name="bloom" label="Bloom level" options={toOptions(BLOOM_LABELS)} placeholder="Not set" />
            <TextField<QuestionFormValues> name="skills" label="Skills" hint="Comma-separated" />
            <TextField<QuestionFormValues> name="topics" label="Topics" hint="Comma-separated" />
            <TextField<QuestionFormValues> name="tags" label="Tags" hint="Comma-separated" className="sm:col-span-2" />
          </FormSection>
          <FormSection title="Answer" columns={1}>
            <QuestionBodyEditor type={type} draft={draft} onChange={setDraft} />
          </FormSection>
        </Card>
        <FormActions>
          <Button variant="secondary" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" loading={submitting}>
            {mode === "create" ? "Create question" : "Save changes"}
          </Button>
        </FormActions>
      </form>
    </FormProvider>
  );
}
