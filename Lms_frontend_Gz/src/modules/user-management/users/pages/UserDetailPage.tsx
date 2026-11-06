import { useNavigate, useParams } from "react-router-dom";

import { RoleBadge, StatusBadge } from "@/modules/user-management/common/components/UserBadges";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { PersonPermissionsCard } from "@/modules/user-management/permissions/components/PersonPermissionsCard";
import { useGetUserQuery, type UserResource } from "@/modules/user-management/users/api/usersApi";
import { SetPasswordDialog } from "@/modules/user-management/users/components/SetPasswordDialog";
import { AccountCard } from "@/modules/user-management/users/components/detail/AccountCard";
import { AddressCard } from "@/modules/user-management/users/components/detail/AddressCard";
import { EmploymentCard } from "@/modules/user-management/users/components/detail/EmploymentCard";
import { OrganisationCard } from "@/modules/user-management/users/components/detail/OrganisationCard";
import { PersonalInfoCard } from "@/modules/user-management/users/components/detail/PersonalInfoCard";
import { ScopesCard } from "@/modules/user-management/users/components/detail/ScopesCard";
import { StudentCard } from "@/modules/user-management/users/components/detail/StudentCard";
import { useUserActions } from "@/modules/user-management/users/hooks/useUserActions";
import { Alert, Avatar, Badge, Button, ConfirmDialog, EmptyState, Menu, PageHeader, PageLoader } from "@/shared/ui";

export function UserDetailPage({ resource }: { resource: UserResource }) {
  const { userId = "" } = useParams();
  const navigate = useNavigate();
  const { data: user, isLoading, isError } = useGetUserQuery({ resource, userId });
  const actions = useUserActions(resource);
  const { isSuperAdmin } = useCan();

  if (isLoading) return <PageLoader />;
  if (isError || !user) {
    return <EmptyState icon="alert" title="User not found" description="It may have been deleted or is outside your access." action={<Button onClick={() => navigate(`/${resource}`)}>Back to list</Button>} />;
  }

  const menuItems = actions.itemsFor({
    user_id: user.user_id,
    full_name: user.personal_info.full_name,
    status: user.status,
    allowed_actions: user.allowed_actions,
  });
  const editItem = menuItems.find((item) => item.label === "Edit" && !item.hidden);

  return (
    <>
      <PageHeader
        backTo={`/${resource}`}
        backLabel={resource === "admins" ? "Admins" : "Users"}
        title={
          <span className="flex items-center gap-3">
            <Avatar name={user.personal_info.full_name} size="lg" />
            <span>
              {user.personal_info.full_name}
              <span className="mt-1 flex flex-wrap items-center gap-2 text-sm font-normal">
                <RoleBadge role={user.role} />
                <StatusBadge status={user.status} />
                {user.account.must_change_password && <Badge tone="amber">Temporary password</Badge>}
              </span>
            </span>
          </span>
        }
        actions={
          <>
            {editItem && (
              <Button variant="secondary" icon="edit" onClick={editItem.onSelect}>
                Edit
              </Button>
            )}
            <Menu trigger={<Button variant="secondary" icon="more">Actions</Button>} items={menuItems.filter((item) => item.label !== "Edit")} />
          </>
        }
      />

      {user.status === "suspended" && user.status_reason && (
        <Alert tone="warning" title="Suspended" className="mb-6">
          {user.status_reason}
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <PersonalInfoCard user={user} />
          {user.address && <AddressCard address={user.address} />}
          {user.employment && <EmploymentCard employment={user.employment} />}
          {user.student && <StudentCard student={user.student} />}
        </div>
        <div className="space-y-6">
          <AccountCard user={user} />
          <OrganisationCard user={user} resource={resource} />
          {!isSuperAdmin && user.scopes.length > 0 && <ScopesCard scopes={user.scopes} />}
        </div>
      </div>
      {isSuperAdmin && <div className="mt-6"><PersonPermissionsCard userId={user.user_id} role={user.role} name={user.personal_info.full_name} /></div>}
      <ConfirmDialog {...actions.confirmDialogProps} />
      <SetPasswordDialog {...actions.passwordDialogProps} />
    </>
  );
}
