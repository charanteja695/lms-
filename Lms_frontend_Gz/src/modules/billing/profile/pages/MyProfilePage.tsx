import { useNotify } from "@/core/hooks/useNotify";
import { BillingTabs } from "@/modules/billing/common/components/BillingTabs";
import { useBillingRights } from "@/modules/billing/common/hooks/useBillingRights";
import { useGetMyBillingProfileQuery, useSaveMyBillingProfileMutation } from "@/modules/billing/profile/api/profileApi";
import { ProfileForm } from "@/modules/billing/profile/components/ProfileForm";
import { Alert, PageHeader, PageLoader } from "@/shared/ui";

export function MyProfilePage() {
  const notify = useNotify();
  const { data, isLoading, isError } = useGetMyBillingProfileQuery();
  const [save, { isLoading: saving }] = useSaveMyBillingProfileMutation();
  const { canUpdate } = useBillingRights();
  if (isLoading) return <PageLoader />;

  return (
    <>
      <PageHeader title="Billing" description="Your organisation's legal details, printed on every GST invoice." />
      <BillingTabs />
      {isError && <Alert tone="info" className="mb-4" title="Not set yet">Invoices can't be issued until this is filled in.</Alert>}
      <ProfileForm key={data?.updated_at ?? "new"} profile={data} saving={saving} readOnly={!canUpdate} onSave={(input) => void save(input).unwrap().then(() => notify.success("Billing profile saved"), notify.apiError)} />
    </>
  );
}
