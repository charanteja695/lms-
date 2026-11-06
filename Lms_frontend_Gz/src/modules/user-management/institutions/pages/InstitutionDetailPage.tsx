import { useNavigate, useParams } from "react-router-dom";

import { StatusBadge } from "@/modules/user-management/common/components/UserBadges";
import { INSTITUTION_TYPE_LABELS } from "@/modules/user-management/common/labels";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import { useGetInstitutionQuery } from "@/modules/user-management/institutions/api/institutionsApi";
import { InstitutionDetailsCard } from "@/modules/user-management/institutions/components/detail/InstitutionDetailsCard";
import { MemberStats } from "@/modules/user-management/institutions/components/detail/MemberStats";
import { OwnershipCard } from "@/modules/user-management/institutions/components/detail/OwnershipCard";
import { useOrganizationActions } from "@/modules/user-management/institutions/hooks/useOrganizationActions";
import { Alert, Button, ConfirmDialog, EmptyState, Menu, PageHeader, PageLoader } from "@/shared/ui";

export function InstitutionDetailPage({ organizationIdOverride }: { organizationIdOverride?: string }) {
  const params = useParams();
  const organizationId = organizationIdOverride ?? params.organizationId ?? "";
  const navigate = useNavigate();
  const { permissions } = usePermissions();
  const { data: institution, isLoading, isError } = useGetInstitutionQuery(organizationId, { skip: !organizationId });
  const actions = useOrganizationActions("institution");

  if (isLoading) return <PageLoader />;
  if (isError || !institution) {
    return <EmptyState icon="alert" title="Institution not found" description="It may have been deleted or is outside your access." action={<Button onClick={() => navigate("/")}>Go to dashboard</Button>} />;
  }

  const items = actions.itemsFor(institution);
  const edit = items.find((item) => item.label === "Edit" && !item.hidden);
  const menuItems = items.filter((item) => item.label !== "Edit" && !item.hidden);
  // who owns it and when it changed matters to those who run it, not to its members
  const runsIt = institution.allowed_actions.includes("update");

  return (
    <>
      <PageHeader
        backTo={organizationIdOverride ? undefined : "/institutions"}
        backLabel="Institutions"
        title={
          <span className="flex flex-wrap items-center gap-3">
            {institution.name}
            <StatusBadge status={institution.status} />
          </span>
        }
        description={`${institution.code} · ${INSTITUTION_TYPE_LABELS[institution.type]}`}
        actions={
          <>
            {permissions.academics.view && (
              <Button
                variant="secondary"
                icon="layers"
                onClick={() => navigate(`/academics?organization_id=${institution.organization_id}&organization_label=${encodeURIComponent(institution.name)}`)}
              >
                Academic structure
              </Button>
            )}
            {institution.allowed_actions.includes("add_member") && (
              <Button variant="secondary" icon="plus" onClick={() => navigate("/users/new")}>
                Add member
              </Button>
            )}
            {edit && (
              <Button variant="secondary" icon="edit" onClick={edit.onSelect}>
                Edit
              </Button>
            )}
            {menuItems.length > 0 && <Menu trigger={<Button variant="secondary" icon="more">Actions</Button>} items={menuItems} />}
          </>
        }
      />

      {institution.status === "suspended" && (
        <Alert tone="warning" title="Suspended" className="mb-6">
          {institution.status_reason ?? "Members cannot sign in."}
        </Alert>
      )}

      <MemberStats institution={institution} />
      <div className={runsIt ? "grid gap-6 lg:grid-cols-3" : undefined}>
        <InstitutionDetailsCard institution={institution} />
        {runsIt && <OwnershipCard institution={institution} />}
      </div>
      <ConfirmDialog {...actions.confirmDialogProps} />
    </>
  );
}
