import { Navigate } from "react-router-dom";

import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { EmployerDetailPage } from "@/modules/user-management/employers/pages/EmployerDetailPage";
import { InstitutionDetailPage } from "@/modules/user-management/institutions/pages/InstitutionDetailPage";

/** Members see their own organisation: an institution for school roles, an employer for hiring roles. */
export function MyOrganizationPage() {
  const { user } = useAuth();
  const organization = user?.institution;
  if (!organization) return <Navigate to="/" replace />;
  return organization.organization_type === "employer" ? (
    <EmployerDetailPage organizationIdOverride={organization.organization_id} />
  ) : (
    <InstitutionDetailPage organizationIdOverride={organization.organization_id} />
  );
}
