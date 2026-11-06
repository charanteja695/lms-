import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useCreateQuestionMutation } from "@/modules/assessments/questions/api/questionsApi";
import { QuestionForm } from "@/modules/assessments/questions/components/form/QuestionForm";
import { emptyQuestionForm, toQuestionCreateBody } from "@/modules/assessments/questions/form/questionForm";
import { useQuestionFormErrors } from "@/modules/assessments/questions/hooks/useQuestionFormErrors";
import { PageHeader } from "@/shared/ui";

export function QuestionCreatePage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const [create, { isLoading }] = useCreateQuestionMutation();
  const { formError, setFormError, handle } = useQuestionFormErrors();
  const defaults = useMemo(emptyQuestionForm, []);

  return (
    <>
      <PageHeader title="New question" backTo="/questions" backLabel="Question bank" />
      <QuestionForm
        mode="create"
        defaultValues={defaults}
        submitting={isLoading}
        formError={formError}
        onCancel={() => navigate("/questions")}
        onSubmit={async (values, draft, form) => {
          setFormError(null);
          try {
            await create(toQuestionCreateBody(values, draft)).unwrap();
            notify.success("Question created", "Add it to a test, or submit it for review.");
            navigate("/questions", { replace: true });
          } catch (error) {
            handle(error, form.setError);
          }
        }}
      />
    </>
  );
}
