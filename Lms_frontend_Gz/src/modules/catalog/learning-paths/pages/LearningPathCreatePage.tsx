import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useCreateLearningPathMutation } from "@/modules/catalog/learning-paths/api/learningPathsApi";
import { LearningPathForm } from "@/modules/catalog/learning-paths/components/form/LearningPathForm";
import { emptyLearningPathForm, toLearningPathCreateBody } from "@/modules/catalog/learning-paths/form/learningPathForm";
import { useLearningPathFormErrors } from "@/modules/catalog/learning-paths/hooks/useLearningPathFormErrors";
import { PageHeader } from "@/shared/ui";

export function LearningPathCreatePage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const [create, { isLoading }] = useCreateLearningPathMutation();
  const { formError, setFormError, handle } = useLearningPathFormErrors();
  const defaults = useMemo(emptyLearningPathForm, []);

  return (
    <>
      <PageHeader title="New learning path" backTo="/learning-paths" backLabel="Learning paths" />
      <LearningPathForm
        mode="create"
        defaultValues={defaults}
        submitting={isLoading}
        formError={formError}
        onCancel={() => navigate("/learning-paths")}
        onSubmit={async (values, form) => {
          setFormError(null);
          try {
            const created = await create(toLearningPathCreateBody(values)).unwrap();
            notify.success(`${created.title} created`, "Add courses to it next.");
            navigate(`/learning-paths/${created.learning_path_id}`, { replace: true });
          } catch (error) {
            handle(error, form.setError);
          }
        }}
      />
    </>
  );
}
