import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useGetInstitutionQuery, useUpdateInstitutionMutation } from "@/modules/user-management/institutions/api/institutionsApi";
import { InstitutionForm } from "@/modules/user-management/institutions/components/form/InstitutionForm";
import { institutionToForm, toInstitutionUpdateBody } from "@/modules/user-management/institutions/form/institutionFormMappers";
import { useFormErrorHandler } from "@/modules/user-management/institutions/hooks/useInstitutionFormErrors";
import { EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function InstitutionEditPage() {
  const { organizationId = "" } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();
  const { data: institution, isLoading, isError } = useGetInstitutionQuery(organizationId);
  const [update, { isLoading: saving }] = useUpdateInstitutionMutation();
  const { formError, setFormError, handle } = useFormErrorHandler();
  const initial = useMemo(() => (institution ? institutionToForm(institution) : null), [institution]);

  if (isLoading) return <PageLoader />;
  if (isError || !institution || !initial) return <EmptyState icon="alert" title="Institution not found" />;

  return (
    <>
      <PageHeader title={`Edit ${institution.name}`} backTo={`/institutions/${organizationId}`} backLabel="Institution" />
      <InstitutionForm
        mode="edit"
        defaultValues={initial}
        submitting={saving}
        formError={formError}
        onCancel={() => navigate(`/institutions/${organizationId}`)}
        onSubmit={async (values, form) => {
          setFormError(null);
          const body = toInstitutionUpdateBody(initial, values);
          if (!Object.keys(body).length) {
            notify.info("No changes to save");
            return;
          }
          try {
            await update({ organizationId, body }).unwrap();
            notify.success("Changes saved");
            navigate(`/institutions/${organizationId}`, { replace: true });
          } catch (error) {
            handle(error, form.setError);
          }
        }}
      />
    </>
  );
}
