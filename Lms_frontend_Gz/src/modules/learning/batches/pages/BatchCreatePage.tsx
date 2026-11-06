import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useCreateBatchMutation } from "@/modules/learning/batches/api/batchesApi";
import { BatchForm } from "@/modules/learning/batches/components/form/BatchForm";
import { emptyBatchForm, toBatchCreateBody } from "@/modules/learning/batches/form/batchForm";
import { useBatchFormErrors } from "@/modules/learning/batches/hooks/useBatchFormErrors";
import { PageHeader } from "@/shared/ui";
import { useCan } from "@/modules/user-management/common/permissions/useCan";

export function BatchCreatePage() {
  const { can } = useCan();
  const navigate = useNavigate();
  const notify = useNotify();
  const [create, { isLoading }] = useCreateBatchMutation();
  const { formError, setFormError, handle } = useBatchFormErrors();
  const defaults = useMemo(emptyBatchForm, []);

  return (
    <>
      <PageHeader title="New batch" backTo="/batches" backLabel="Batches" />
      <BatchForm
        defaultValues={defaults}
        showInstitutionField={can("accounts.manage")}
        submitting={isLoading}
        formError={formError}
        onCancel={() => navigate("/batches")}
        onSubmit={async (values, form) => {
          setFormError(null);
          try {
            const created = await create(toBatchCreateBody(values)).unwrap();
            notify.success(`${created.name} created`, "Enrol students next.");
            navigate("/batches", { replace: true });
          } catch (error) {
            handle(error, form.setError);
          }
        }}
      />
    </>
  );
}
