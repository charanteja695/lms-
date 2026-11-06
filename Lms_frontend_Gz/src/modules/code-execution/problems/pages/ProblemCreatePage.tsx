import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useCreateProblemMutation } from "@/modules/code-execution/problems/api/problemsApi";
import { ProblemForm } from "@/modules/code-execution/problems/components/form/ProblemForm";
import { emptyProblemForm, toProblemCreateBody } from "@/modules/code-execution/problems/form/problemForm";
import { useProblemFormErrors } from "@/modules/code-execution/problems/hooks/useProblemFormErrors";
import { PageHeader } from "@/shared/ui";

export function ProblemCreatePage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const [create, { isLoading }] = useCreateProblemMutation();
  const { formError, setFormError, handle } = useProblemFormErrors();
  const defaults = useMemo(emptyProblemForm, []);

  return (
    <>
      <PageHeader title="New problem" backTo="/problems" backLabel="Problems" />
      <ProblemForm
        mode="create"
        defaultValues={defaults}
        submitting={isLoading}
        formError={formError}
        onCancel={() => navigate("/problems")}
        onSubmit={async (values, form) => {
          setFormError(null);
          try {
            const created = await create(toProblemCreateBody(values)).unwrap();
            notify.success(`${created.title} created`, "Add test cases next.");
            navigate(`/problems/${created.problem_id}`, { replace: true });
          } catch (error) {
            handle(error, form.setError);
          }
        }}
      />
    </>
  );
}
