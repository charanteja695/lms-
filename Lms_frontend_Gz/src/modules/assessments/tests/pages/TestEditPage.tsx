import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useGetTestQuery, useUpdateTestMutation } from "@/modules/assessments/tests/api/testsApi";
import { TestForm } from "@/modules/assessments/tests/components/form/TestForm";
import { testToForm, toTestUpdateBody } from "@/modules/assessments/tests/form/testForm";
import { useTestFormErrors } from "@/modules/assessments/tests/hooks/useTestFormErrors";
import { EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function TestEditPage() {
  const { testId = "" } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();
  const { data: test, isLoading, isError } = useGetTestQuery(testId, { skip: !testId });
  const [update, { isLoading: saving }] = useUpdateTestMutation();
  const { formError, setFormError, handle } = useTestFormErrors();
  const initial = useMemo(() => (test ? testToForm(test) : null), [test]);

  if (isLoading) return <PageLoader />;
  if (isError || !test || !initial) return <EmptyState icon="alert" title="Test not found" />;

  return (
    <>
      <PageHeader title={`Edit ${test.title}`} backTo={`/tests/${testId}`} backLabel="Test" />
      <TestForm
        mode="edit"
        defaultValues={initial}
        submitting={saving}
        formError={formError}
        onCancel={() => navigate(`/tests/${testId}`)}
        onSubmit={async (values, form) => {
          setFormError(null);
          const body = toTestUpdateBody(initial, values);
          if (!Object.keys(body).length) {
            notify.info("No changes to save");
            return;
          }
          try {
            await update({ testId, body }).unwrap();
            notify.success("Changes saved");
            navigate(`/tests/${testId}`, { replace: true });
          } catch (error) {
            handle(error, form.setError);
          }
        }}
      />
    </>
  );
}
