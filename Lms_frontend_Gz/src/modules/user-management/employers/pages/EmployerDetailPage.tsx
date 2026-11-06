import { useNavigate, useParams } from "react-router-dom";

import { StatusBadge } from "@/modules/user-management/common/components/UserBadges";
import { useGetEmployerQuery } from "@/modules/user-management/employers/api/employersApi";
import { EmployerDetailsCard } from "@/modules/user-management/employers/components/detail/EmployerDetailsCard";
import { OwnershipCard } from "@/modules/user-management/institutions/components/detail/OwnershipCard";
import { useOrganizationActions } from "@/modules/user-management/institutions/hooks/useOrganizationActions";
import { CompanyHiringProfileCard } from "@/modules/job-portal/admin/components/CompanyHiringProfileCard";
import { Alert, Button, ConfirmDialog, EmptyState, Menu, PageHeader, PageLoader, StatTile } from "@/shared/ui";

export function EmployerDetailPage({ organizationIdOverride }: { organizationIdOverride?: string }) {
  const params = useParams();
  const organizationId = organizationIdOverride ?? params.organizationId ?? "";
  const navigate = useNavigate();
  const { data: employer, isLoading, isError } = useGetEmployerQuery(organizationId, { skip: !organizationId });
  const actions = useOrganizationActions("employer");

  if (isLoading) return <PageLoader />;
  if (isError || !employer) {
    return <EmptyState icon="alert" title="Employer not found" description="It may have been deleted or is outside your access." action={<Button onClick={() => navigate("/")}>Go to dashboard</Button>} />;
  }

  const items = actions.itemsFor(employer);
  const edit = items.find((item) => item.label === "Edit" && !item.hidden);
  const canOpenMembers = employer.allowed_actions.includes("view_members");
  const usersLink = () => `/users?organization_id=${employer.organization_id}&organization_label=${encodeURIComponent(employer.name)}`;

  return (
    <>
      <PageHeader
        backTo={organizationIdOverride ? undefined : "/employers"}
        backLabel="Companies"
        title={
          <span className="flex flex-wrap items-center gap-3">
            {employer.name}
            <StatusBadge status={employer.status} />
          </span>
        }
        actions={
          <>
            <Button
              variant="secondary"
              onClick={() => navigate(`/jobs/employer?employer_org_id=${employer.organization_id}`)}
            >
              View Jobs
            </Button>
            <Button
              variant="primary"
              onClick={() => navigate(`/jobs/employer/new?employer_org_id=${employer.organization_id}&company_name=${encodeURIComponent(employer.name)}`)}
            >
              + Create Job
            </Button>
            {edit && (
              <Button variant="secondary" icon="edit" onClick={edit.onSelect}>
                Edit
              </Button>
            )}
            <Menu trigger={<Button variant="secondary" icon="more">Actions</Button>} items={items.filter((item) => item.label !== "Edit")} />
          </>
        }
      />

      {employer.status === "suspended" && (
        <Alert tone="warning" title="Suspended" className="mb-6">
          {employer.status_reason ?? "Members cannot sign in."}
        </Alert>
      )}

      {employer.member_counts.total > 0 && (
        <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {/* company logins are no longer created; older ones stay reachable to suspend or remove */}
          <StatTile icon="users" label="Older company logins" value={employer.member_counts.total} to={canOpenMembers ? usersLink() : undefined} />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <EmployerDetailsCard employer={employer} />
          <CompanyHiringProfileCard organizationId={employer.organization_id} industry={employer.industry} />
        </div>
        <OwnershipCard institution={employer} />
      </div>
      <ConfirmDialog {...actions.confirmDialogProps} />
    </>
  );
}
