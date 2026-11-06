import { FormProvider, useForm } from "react-hook-form";

import { toOptions } from "@/core/lib/options";
import { useNotify } from "@/core/hooks/useNotify";
import { COMPARE_MODE_LABELS } from "@/modules/code-execution/common/labels";
import type { CompareMode } from "@/modules/code-execution/common/types";
import { useCreateTestCaseMutation, useUpdateTestCaseMutation } from "@/modules/code-execution/problems/api/problemsApi";
import type { TestCase } from "@/modules/code-execution/problems/types";
import { CheckboxField, SelectField, TextField, TextareaField } from "@/shared/form";
import { Button, Modal } from "@/shared/ui";

interface TestCaseFormValues {
  input: string;
  expected: string;
  is_sample: boolean;
  compare_mode: string;
  weight: string;
  explanation: string;
}

export function TestCaseFormDialog({ open, onClose, problemId, testCase: existing }: {
  open: boolean;
  onClose: () => void;
  problemId: string;
  /** Omit to create a new test case. */
  testCase?: TestCase;
}) {
  const notify = useNotify();
  const [createTestCase, { isLoading: creating }] = useCreateTestCaseMutation();
  const [updateTestCase, { isLoading: updating }] = useUpdateTestCaseMutation();
  const isLoading = creating || updating;
  const form = useForm<TestCaseFormValues>({
    values: {
      input: existing?.input ?? "",
      expected: existing?.expected ?? "",
      is_sample: existing?.is_sample ?? false,
      compare_mode: existing?.compare_mode ?? "",
      weight: String(existing?.weight ?? 1),
      explanation: existing?.explanation ?? "",
    },
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={existing ? "Edit test case" : "Add test case"}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button type="submit" form="test-case-form" loading={isLoading}>
            {existing ? "Save" : "Add test case"}
          </Button>
        </>
      }
    >
      <FormProvider {...form}>
        <form
          id="test-case-form"
          noValidate
          className="space-y-4"
          onSubmit={form.handleSubmit(async (values) => {
            const body = {
              input: values.input,
              expected: values.expected,
              is_sample: values.is_sample,
              compare_mode: (values.compare_mode || null) as CompareMode | null,
              weight: Number(values.weight),
              explanation: values.explanation || null,
            };
            try {
              if (existing) {
                await updateTestCase({ problemId, testCaseId: existing.test_case_id, body }).unwrap();
                notify.success("Test case updated");
              } else {
                await createTestCase({ problemId, body }).unwrap();
                notify.success("Test case added");
              }
              onClose();
            } catch (error) {
              notify.apiError(error);
            }
          })}
        >
          <TextareaField<TestCaseFormValues> name="input" label="Input" rows={4} hint="stdin for a code problem; extra seed data for a SQL problem." />
          <TextareaField<TestCaseFormValues> name="expected" label="Expected output" required rows={4} />
          <div className="grid gap-4 sm:grid-cols-2">
            <SelectField<TestCaseFormValues> name="compare_mode" label="Compare mode override" options={toOptions(COMPARE_MODE_LABELS)} placeholder="Use the problem's default" />
            <TextField<TestCaseFormValues> name="weight" label="Weight" type="number" required hint="Up to 100." />
          </div>
          <CheckboxField<TestCaseFormValues> name="is_sample" label="Sample case" hint="Shown to students on the problem page, with its input and expected output visible." />
          <TextField<TestCaseFormValues> name="explanation" label="Explanation" hint="Optional. Shown with the sample." />
        </form>
      </FormProvider>
    </Modal>
  );
}
