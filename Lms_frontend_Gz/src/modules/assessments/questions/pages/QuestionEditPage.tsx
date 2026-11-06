import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useGetQuestionQuery, useUpdateQuestionMutation } from "@/modules/assessments/questions/api/questionsApi";
import { QuestionForm } from "@/modules/assessments/questions/components/form/QuestionForm";
import { questionToForm, toQuestionUpdateBody } from "@/modules/assessments/questions/form/questionForm";
import { useQuestionFormErrors } from "@/modules/assessments/questions/hooks/useQuestionFormErrors";
import { EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function QuestionEditPage() {
  const { questionId = "" } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();
  const { data: question, isLoading, isError } = useGetQuestionQuery(questionId, { skip: !questionId });
  const [update, { isLoading: saving }] = useUpdateQuestionMutation();
  const { formError, setFormError, handle } = useQuestionFormErrors();
  const initial = useMemo(() => (question ? questionToForm(question) : null), [question]);

  if (isLoading) return <PageLoader />;
  if (isError || !question || !initial) return <EmptyState icon="alert" title="Question not found" />;

  return (
    <>
      <PageHeader title="Edit question" backTo={`/questions/${questionId}`} backLabel="Question" />
      <QuestionForm
        mode="edit"
        defaultValues={initial.values}
        defaultDraft={initial.draft}
        submitting={saving}
        formError={formError}
        onCancel={() => navigate(`/questions/${questionId}`)}
        onSubmit={async (values, draft, form) => {
          setFormError(null);
          try {
            const body = toQuestionUpdateBody(initial.values, values, draft);
            await update({ questionId, body }).unwrap();
            notify.success("Changes saved");
            navigate(`/questions/${questionId}`, { replace: true });
          } catch (error) {
            handle(error, form.setError);
          }
        }}
      />
    </>
  );
}
