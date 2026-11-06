import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { OrganizationNameCell } from "@/modules/user-management/common/components/OrganizationNameCell";

/** A member's own organisation from their session; any other through the platform-staff directory. */
export function OrgName({ organizationId }: { organizationId: string }) {
  const { user } = useAuth();
  if (user?.institution?.organization_id === organizationId) return <span className="text-slate-900">{user.institution.name}</span>;
  return <OrganizationNameCell organizationId={organizationId} />;
}
