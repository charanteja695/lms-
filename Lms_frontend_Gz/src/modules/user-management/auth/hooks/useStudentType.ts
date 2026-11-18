import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";

export interface StudentTypeInfo {
  /** True while the authentication session or server permissions are still being loaded. */
  isResolving: boolean;
  /** Whether the user is signed in with the 'student' role. */
  isStudent: boolean;
  /** True for independent students who registered directly without belonging to an institution. */
  isIndependentStudent: boolean;
  /** True for students enrolled under a valid institution (has an organization_id). */
  isInstitutionStudent: boolean;
  /** True for Institution Heads managing an institution. */
  isInstitutionHead: boolean;
  /** True for Admins or Super Admins. */
  isAdmin: boolean;
  /** The institution's organization public ID if institution-linked, otherwise null. */
  organizationId: string | number | null;
  /** The institution's name if institution-linked, otherwise null. */
  institutionName: string | null;
}

/**
 * Centrally and deterministically resolves student categorization based on authenticated profile
 * and organization_id according to ExamLMS business rules:
 * - No organization_id and student role = Independent Student
 * - Valid organization_id and student role = Institution Student
 * - Institution Head role = Institution Head
 */
export function useStudentType(): StudentTypeInfo {
  const { user, role, sessionStatus, isAuthenticated } = useAuth();
  const { permissions, isLoading: permissionsLoading } = usePermissions();

  const isResolving = sessionStatus === "checking" || permissionsLoading;

  // An institution-linked student has a valid non-empty organization_id
  // and is not a synthetic/standalone "INDIVIDUAL" placeholder.
  const orgId = user?.institution?.organization_id ?? null;
  const isIndividualCode = user?.institution?.code === "INDIVIDUAL" || (user?.institution as any)?.organization_type === "individual";
  const hasValidOrgId = Boolean(orgId && !isIndividualCode);

  const isStudent = isAuthenticated && (role === "student" || permissions.role === "student");
  const isIndependentStudent = isStudent && !hasValidOrgId;
  const isInstitutionStudent = isStudent && hasValidOrgId;
  const isInstitutionHead = isAuthenticated && (role === "institution_head" || permissions.role === "institution_head");
  const isAdmin = isAuthenticated && (role === "admin" || role === "super_admin" || permissions.role === "admin" || permissions.role === "super_admin");

  return {
    isResolving,
    isStudent,
    isIndependentStudent,
    isInstitutionStudent,
    isInstitutionHead,
    isAdmin,
    organizationId: hasValidOrgId ? orgId : null,
    institutionName: hasValidOrgId ? (user?.institution?.name || "Your Institution") : null,
  };
}
