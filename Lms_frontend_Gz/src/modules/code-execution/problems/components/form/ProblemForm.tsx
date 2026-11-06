import { FormProvider, useForm, type UseFormReturn } from "react-hook-form";

import { toOptions } from "@/core/lib/options";
import { COMPARE_MODE_LABELS, DIFFICULTY_LABELS, PROBLEM_TYPE_LABELS } from "@/modules/code-execution/common/labels";
import { AllowedLanguagesField } from "@/modules/code-execution/problems/components/form/AllowedLanguagesField";
import type { ProblemFormValues } from "@/modules/code-execution/problems/form/problemForm";
import { FormSection, SelectField, TextareaField, TextField, FormActions } from "@/shared/form";
import { Alert, Button, Card } from "@/shared/ui";

export function ProblemForm({ mode, defaultValues, submitting, formError, onSubmit, onCancel }: {
  mode: "create" | "edit";
  defaultValues: ProblemFormValues;
  submitting: boolean;
  formError?: string | null;
  onSubmit: (values: ProblemFormValues, form: UseFormReturn<ProblemFormValues>) => Promise<void>;
  onCancel: () => void;
}) {
  const form = useForm<ProblemFormValues>({ defaultValues, mode: "onTouched" });
  const problemType = form.watch("problem_type");
  const compareMode = form.watch("compare_mode");

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
          <FormSection title="Problem" description="Shown to students once published.">
            <TextField<ProblemFormValues> name="title" label="Title" required maxLength={200} className="sm:col-span-2" />
            <TextareaField<ProblemFormValues> name="statement" label="Statement" required rows={8} maxLength={50000} className="sm:col-span-2" />
            {mode === "create" ? (
              <SelectField<ProblemFormValues> name="problem_type" label="Type" options={toOptions(PROBLEM_TYPE_LABELS)} required />
            ) : (
              <TextField<ProblemFormValues> name="problem_type" label="Type" disabled hint="Cannot be changed after creation." />
            )}
            <SelectField<ProblemFormValues> name="difficulty" label="Difficulty" options={toOptions(DIFFICULTY_LABELS)} required />
            <TextField<ProblemFormValues> name="tags" label="Tags" hint="Comma-separated, e.g. arrays, sorting" className="sm:col-span-2" />
          </FormSection>
          <FormSection title="Limits">
            <TextField<ProblemFormValues> name="time_limit_ms" label="Time limit (ms)" type="number" required />
            <TextField<ProblemFormValues> name="memory_limit_mb" label="Memory limit (MB)" type="number" required />
          </FormSection>
          <FormSection title="Languages" description="Which languages a student may use.">
            <div className="sm:col-span-2">
              <AllowedLanguagesField />
            </div>
          </FormSection>
          <FormSection title="Judging">
            <SelectField<ProblemFormValues> name="compare_mode" label="Compare mode" options={toOptions(COMPARE_MODE_LABELS)} required />
            {compareMode === "float" && <TextField<ProblemFormValues> name="float_tolerance" label="Float tolerance" type="number" required />}
            {problemType === "sql" && (
              <TextareaField<ProblemFormValues> name="setup_sql" label="Setup SQL" rows={6} hint="Schema and seed data run before every test case." className="sm:col-span-2" />
            )}
          </FormSection>
        </Card>
        <FormActions>
          <Button variant="secondary" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" loading={submitting}>
            {mode === "create" ? "Create problem" : "Save changes"}
          </Button>
        </FormActions>
      </form>
    </FormProvider>
  );
}
