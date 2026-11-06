import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useGetLearningPathQuery, useUpdateLearningPathMutation } from "@/modules/catalog/learning-paths/api/learningPathsApi";
import { LearningPathForm } from "@/modules/catalog/learning-paths/components/form/LearningPathForm";
import { learningPathToForm, toLearningPathUpdateBody } from "@/modules/catalog/learning-paths/form/learningPathForm";
import { useLearningPathFormErrors } from "@/modules/catalog/learning-paths/hooks/useLearningPathFormErrors";
import { EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function LearningPathEditPage() {
  const { learningPathId = "" } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();
  const { data: path, isLoading, isError } = useGetLearningPathQuery(learningPathId);
  const [update, { isLoading: saving }] = useUpdateLearningPathMutation();
  const { formError, setFormError, handle } = useLearningPathFormErrors();
  const initial = useMemo(() => (path ? learningPathToForm(path) : null), [path]);

  if (isLoading) return <PageLoader />;
  if (isError || !path || !initial) return <EmptyState icon="alert" title="Learning path not found" />;

  return (
    <>
      <PageHeader title={`Edit ${path.title}`} backTo={`/learning-paths/${learningPathId}`} backLabel="Learning path" />
      <LearningPathForm
        mode="edit"
        defaultValues={initial}
        submitting={saving}
        formError={formError}
        onCancel={() => navigate(`/learning-paths/${learningPathId}`)}
        onSubmit={async (values, form) => {
          setFormError(null);
          const body = toLearningPathUpdateBody(initial, values);
          if (!Object.keys(body).length) {
            notify.info("No changes to save");
            return;
          }
          try {
            await update({ id: learningPathId, body }).unwrap();
            notify.success("Changes saved");
            navigate(`/learning-paths/${learningPathId}`, { replace: true });
          } catch (error) {
            handle(error, form.setError);
          }
        }}
      />
    </>
  );
}
