import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { applyServerErrors, toApiError } from "@/core/lib/apiError";
import { useCreateEmployerMutation } from "@/modules/user-management/employers/api/employersApi";
import { EmployerForm } from "@/modules/user-management/employers/components/form/EmployerForm";
import { emptyEmployerForm, isEmployerField, toEmployerCreateBody } from "@/modules/user-management/employers/form/employerForm";
import { PageHeader } from "@/shared/ui";

export function EmployerCreatePage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const [create, { isLoading }] = useCreateEmployerMutation();
  const [formError, setFormError] = useState<string | null>(null);
  const defaults = useMemo(emptyEmployerForm, []);

  return (
    <>
      <PageHeader title="New company" backTo="/employers" backLabel="Companies" />
      <EmployerForm
        mode="create"
        defaultValues={defaults}
        submitting={isLoading}
        formError={formError}
        onCancel={() => navigate("/employers")}
        onSubmit={async (values, form) => {
          setFormError(null);
          try {
            const created = await create(toEmployerCreateBody(values)).unwrap();
            notify.success(`${created.name} created`, "Post its jobs from Jobs.");
            navigate("/employers", { replace: true });
          } catch (error) {
            const apiError = toApiError(error);
            const unmatched = applyServerErrors(apiError, form.setError, isEmployerField);
            if (!apiError.details.length || unmatched.length) setFormError(apiError.message);
            else notify.error(apiError.message, "Check the highlighted fields.");
          }
        }}
      />
    </>
  );
}
