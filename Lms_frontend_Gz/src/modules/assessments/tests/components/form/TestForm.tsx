import { FormProvider, useForm, type UseFormReturn } from "react-hook-form";
import { useState } from "react";

import { toOptions } from "@/core/lib/options";
import {
  PROCTORING_LEVEL_LABELS,
  RESULT_VISIBILITY_LABELS,
  REVIEW_POLICY_LABELS,
  SCORE_COUNTING_LABELS,
  TEST_KIND_LABELS,
} from "@/modules/assessments/common/labels";
import type { TestFormValues } from "@/modules/assessments/tests/form/testForm";
import { CheckboxField, FormSection, SelectField, TextareaField, TextField, FormActions } from "@/shared/form";
import { Alert, Button, Card } from "@/shared/ui";

import { useNotify } from "@/core/hooks/useNotify";
import { ImportQuestionsDialog } from "@/modules/assessments/questions/components/ImportQuestionsDialog";
import { useAddQuestionToTestMutation } from "@/modules/assessments/tests/api/testsApi";
import { useParams } from "react-router-dom";

const TIME_MODE_OPTIONS = [
  { value: "overall", label: "One timer for the whole test" },
  { value: "per_section", label: "Each section has its own timer" },
];

export function TestForm({ mode, defaultValues, submitting, formError, onSubmit, onCancel, fixedTarget }: {
  mode: "create" | "edit";
  /** Set when the test is created from a course builder: it belongs to this topic/module, shown by name. */
  fixedTarget?: string;
  defaultValues: TestFormValues;
  submitting: boolean;
  formError?: string | null;
  onSubmit: (values: TestFormValues, form: UseFormReturn<TestFormValues>) => Promise<void>;
  onCancel: () => void;
}) {
  const form = useForm<TestFormValues>({ defaultValues });
  const [importOpen, setImportOpen] = useState(false);
  const { testId } = useParams();
  const [addQuestion] = useAddQuestionToTestMutation();
  const notify = useNotify();
  const kind = form.watch("kind");
  const timeMode = form.watch("time_mode");
  const proctoring = form.watch("proctoring_level");
  const needsTarget = kind === "topic" || kind === "module" || kind === "final";

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
          <FormSection title="Test" description="What it's for and, if it gates a course, which part.">
            <TextField<TestFormValues> name="title" label="Title" required maxLength={200} className="sm:col-span-2" />
            {fixedTarget ? (
              <div className="rounded-xl bg-brand-50 px-4 py-3 text-sm text-brand-900 ring-1 ring-brand-100 sm:col-span-2">
                <span className="font-semibold">{TEST_KIND_LABELS[kind]}</span> for <span className="font-semibold">{fixedTarget}</span>. When it is published it is attached to the course automatically.
              </div>
            ) : (
              <SelectField<TestFormValues> name="kind" label="Kind" options={toOptions(TEST_KIND_LABELS)} required />
            )}
            {needsTarget && !fixedTarget && <TextField<TestFormValues> name="target_id" label="Target ID" required hint="The catalog topic/module/course this test gates." />}
            <TextareaField<TestFormValues> name="description" label="Description" rows={2} className="sm:col-span-2" />
            <TextareaField<TestFormValues> name="instructions" label="Instructions" hint="Shown to the student before they start." rows={3} className="sm:col-span-2" />
          </FormSection>
          <FormSection title="Timing & attempts">
            <SelectField<TestFormValues> name="time_mode" label="Time mode" options={TIME_MODE_OPTIONS} required />
            {timeMode === "overall" && <TextField<TestFormValues> name="duration_minutes" label="Duration (minutes)" type="number" required />}
            <TextField<TestFormValues> name="pass_mark_percent" label="Pass mark %" type="number" required />
            <TextField<TestFormValues> name="max_attempts" label="Max attempts" type="number" required hint="0 = unlimited." />
            <TextField<TestFormValues> name="cooldown_hours" label="Cooldown (hours)" type="number" required />
            <SelectField<TestFormValues> name="score_counting" label="Score counting" options={toOptions(SCORE_COUNTING_LABELS)} required />
            <TextField<TestFormValues> name="negative_marking_percent" label="Negative marking %" type="number" required hint="MCQ, true/false and fill-in only." />
          </FormSection>
          <FormSection title="Behaviour">
            <SelectField<TestFormValues> name="result_visibility" label="Result visibility" options={toOptions(RESULT_VISIBILITY_LABELS)} required />
            <SelectField<TestFormValues> name="review_policy" label="Review policy" options={toOptions(REVIEW_POLICY_LABELS)} required />
            <SelectField<TestFormValues> name="proctoring_level" label="Proctoring" options={toOptions(PROCTORING_LEVEL_LABELS)} required />
            <div className="flex flex-col gap-3 sm:col-span-2">
              <CheckboxField<TestFormValues> name="shuffle_questions" label="Shuffle question order" />
              <CheckboxField<TestFormValues> name="shuffle_options" label="Shuffle answer options" />
              <CheckboxField<TestFormValues> name="requires_schedule" label="Requires a schedule" hint="Only runnable inside a scheduled exam window." />
              {proctoring === "strict" && (
                <CheckboxField<TestFormValues> name="proctoring_screen_share" label="Require screen sharing" hint="Students share their entire screen for the whole test; it is captured with each photo." />
              )}
            </div>
          </FormSection>
        </Card>
        <FormActions>
          <Button variant="secondary" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" loading={submitting}>
            {mode === "create" ? "Create test" : "Save changes"}
          </Button>
        </FormActions>
        {/* Import Questions button */}
        <Button variant="secondary" onClick={() => setImportOpen(true)} disabled={submitting}>
          Import Questions
        </Button>
        <ImportQuestionsDialog
          open={importOpen}
          onClose={() => setImportOpen(false)}
          onImported={async (ids) => {
            if (!testId) return;
            // Add each imported question to the test
            for (const qid of ids) {
              try {
                await addQuestion({ testId, questionId: qid }).unwrap();
              } catch (e) {
                notify.apiError(e);
              }
            }
            notify.success(`${ids.length} questions attached to the test`);
            setImportOpen(false);
          }}
        />
      </form>
    </FormProvider>
  );
}
