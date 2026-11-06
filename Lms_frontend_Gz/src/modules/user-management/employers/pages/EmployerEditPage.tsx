import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { applyServerErrors, toApiError } from "@/core/lib/apiError";
import { useGetEmployerQuery, useUpdateEmployerMutation } from "@/modules/user-management/employers/api/employersApi";
import { EmployerForm } from "@/modules/user-management/employers/components/form/EmployerForm";
import { employerToForm, isEmployerField, toEmployerUpdateBody } from "@/modules/user-management/employers/form/employerForm";
import { EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function EmployerEditPage() {
  const { organizationId = "" } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();
  const { data: employer, isLoading, isError } = useGetEmployerQuery(organizationId);
  const [update, { isLoading: saving }] = useUpdateEmployerMutation();
  const [formError, setFormError] = useState<string | null>(null);
  const initial = useMemo(() => (employer ? employerToForm(employer) : null), [employer]);

  if (isLoading) return <PageLoader />;
  if (isError || !employer || !initial) return <EmptyState icon="alert" title="Employer not found" />;

  return (
    <>
      <PageHeader title={`Edit ${employer.name}`} backTo={`/employers/${organizationId}`} backLabel="Company" />
      <EmployerForm
        mode="edit"
        defaultValues={initial}
        submitting={saving}
        formError={formError}
        onCancel={() => navigate(`/employers/${organizationId}`)}
        onSubmit={async (values, form) => {
          setFormError(null);
          const body = toEmployerUpdateBody(initial, values);
          if (!Object.keys(body).length) {
            notify.info("No changes to save");
            return;
          }
          try {
            await update({ organizationId, body }).unwrap();
            notify.success("Changes saved");
            navigate(`/employers/${organizationId}`, { replace: true });
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
