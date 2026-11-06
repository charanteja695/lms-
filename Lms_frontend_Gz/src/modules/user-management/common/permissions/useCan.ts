import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";

/**
 * Whether the signed-in person holds a permission, straight from the server's effective list
 * (role defaults + scopes + their own grants − removals). Show buttons and screens from this, never from the role.
 *
 * - `can(key)`: a management permission. A super admin holds every one.
 * - `holds(key)`: a person's own participation (take tests, apply for jobs…). Not implied by being a super admin.
 */
const MATRIX_ROLES = new Set(["admin", "institution_head", "staff", "student"]);

export function useCan() {
  const { permissions } = usePermissions();
  const held = new Set(permissions.permissions);
  const isSuperAdmin = permissions.role === "super_admin";
  return {
    can: (key: string) => isSuperAdmin || held.has(key),
    holds: (key: string) => held.has(key),
    /**
     * One action on one page of the permission matrix (`batches.create`), as the server decides it: admins, heads,
     * staff and students need that exact cell; older company roles still hold the coarse `legacy` key.
     */
    acts: (cell: string, legacy: string) => isSuperAdmin || (MATRIX_ROLES.has(permissions.role) ? held.has(cell) : held.has(legacy)),
    isSuperAdmin,
    /** The kind of organisation they belong to (data reach), or null for platform staff. */
    organizationType: permissions.organization_type,
  };
}
