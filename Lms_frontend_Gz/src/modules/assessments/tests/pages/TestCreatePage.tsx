import { useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { safeInternalPath } from "@/core/lib/safePath";
import { useCreateTestMutation } from "@/modules/assessments/tests/api/testsApi";
import { TestForm } from "@/modules/assessments/tests/components/form/TestForm";
import { emptyTestForm, toTestCreateBody } from "@/modules/assessments/tests/form/testForm";
import { useTestFormErrors } from "@/modules/assessments/tests/hooks/useTestFormErrors";
import type { TestKind } from "@/modules/assessments/common/types";
import { PageHeader } from "@/shared/ui";

/**
 * A new test. From a course builder the link carries what it is for (`kind`, `target_id`, `target`, `pass_mark`) and
 * where to come back to (`from`); otherwise it is a blank test from the Tests list.
 */
export function TestCreatePage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const [params] = useSearchParams();
  const [create, { isLoading }] = useCreateTestMutation();
  const { formError, setFormError, handle } = useTestFormErrors();
  const target = params.get("target") ?? undefined;
  const from = safeInternalPath(params.get("from"));
  const defaults = useMemo(
    () =>
      emptyTestForm(
        target
          ? {
              kind: (params.get("kind") as TestKind | null) ?? "topic",
              target_id: params.get("target_id") ?? "",
              title: `${target}: topic test`,
              pass_mark_percent: params.get("pass_mark") ?? "60",
              duration_minutes: "20",
              max_attempts: "0",
            }
          : {},
      ),
    [params, target],
  );

  return (
    <>
      <PageHeader title={target ? "New topic test" : "New test"} description={target ? `Ends the topic "${target}"` : undefined} backTo="/tests" backLabel="Tests" />
      <TestForm
        mode="create"
        defaultValues={defaults}
        fixedTarget={target}
        submitting={isLoading}
        formError={formError}
        onCancel={() => navigate(from ?? "/tests")}
        onSubmit={async (values, form) => {
          setFormError(null);
          try {
            const created = await create(toTestCreateBody(values)).unwrap();
            notify.success("Test created", "Add its questions, then publish it.");
            navigate(`/tests/${created.test_id}${from ? `?from=${encodeURIComponent(from)}` : ""}`, { replace: true });
          } catch (error) {
            handle(error, form.setError);
          }
        }}
      />
    </>
  );
}
