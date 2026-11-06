import { useParams } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useGetOrgBillingProfileQuery, useSaveOrgBillingProfileMutation } from "@/modules/billing/profile/api/profileApi";
import { ProfileForm } from "@/modules/billing/profile/components/ProfileForm";
import { OrganizationNameCell } from "@/modules/user-management/common/components/OrganizationNameCell";
import { Alert, PageHeader, PageLoader } from "@/shared/ui";

/** A billing manager sets an organisation's billing profile (e.g. before issuing its first invoice). */
export function OrgProfilePage() {
  const { orgId = "" } = useParams();
  const notify = useNotify();
  const { data, isLoading, isError } = useGetOrgBillingProfileQuery(orgId);
  const [save, { isLoading: saving }] = useSaveOrgBillingProfileMutation();
  if (isLoading) return <PageLoader />;

  return (
    <>
      <PageHeader title={<OrganizationNameCell organizationId={orgId} />} description="Billing profile" backTo="/billing/invoices" backLabel="Invoices" />
      {isError && <Alert tone="info" className="mb-4" title="Not set yet">Invoices for this organisation can't be issued until this is filled in.</Alert>}
      <ProfileForm
        key={data?.updated_at ?? "new"}
        profile={data}
        saving={saving}
        onSave={(input) => void save({ orgId, ...input }).unwrap().then(() => notify.success("Billing profile saved"), notify.apiError)}
      />
    </>
  );
}
