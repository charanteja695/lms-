import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useGetProblemAuthorQuery, useUpdateProblemMutation } from "@/modules/code-execution/problems/api/problemsApi";
import { ProblemForm } from "@/modules/code-execution/problems/components/form/ProblemForm";
import { problemToForm, toProblemUpdateBody } from "@/modules/code-execution/problems/form/problemForm";
import { useProblemFormErrors } from "@/modules/code-execution/problems/hooks/useProblemFormErrors";
import { EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function ProblemEditPage() {
  const { problemId = "" } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();
  const { data: problem, isLoading, isError } = useGetProblemAuthorQuery(problemId, { skip: !problemId });
  const [update, { isLoading: saving }] = useUpdateProblemMutation();
  const { formError, setFormError, handle } = useProblemFormErrors();
  const initial = useMemo(() => (problem ? problemToForm(problem) : null), [problem]);

  if (isLoading) return <PageLoader />;
  if (isError || !problem || !initial) return <EmptyState icon="alert" title="Problem not found" />;

  return (
    <>
      <PageHeader title={`Edit ${problem.title}`} backTo={`/problems/${problemId}`} backLabel="Problem" />
      <ProblemForm
        mode="edit"
        defaultValues={initial}
        submitting={saving}
        formError={formError}
        onCancel={() => navigate(`/problems/${problemId}`)}
        onSubmit={async (values, form) => {
          setFormError(null);
          const body = toProblemUpdateBody(initial, values);
          if (!Object.keys(body).length) {
            notify.info("No changes to save");
            return;
          }
          try {
            await update({ problemId, body }).unwrap();
            notify.success("Changes saved");
            navigate(`/problems/${problemId}`, { replace: true });
          } catch (error) {
            handle(error, form.setError);
          }
        }}
      />
    </>
  );
}
