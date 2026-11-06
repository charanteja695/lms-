import { useGetMyPermissionsQuery } from "@/modules/user-management/common/permissions/permissionsApi";
import type { MenuKey, Permissions, Section } from "@/modules/user-management/common/permissions/types";

const EMPTY: Permissions = {
  role: "student",
  organization_type: null,
  scopes: [],
  permissions: [],
  sections: [],
  menu: [],
  users: {
    view_roles: [],
    create_roles: [],
    can_import: false,
    can_export: false,
    filter_statuses: [],
    filter_by_institution: false,
  },
  admins: { view: false, create: false },
  institutions: { create: false, export: false, filter_statuses: [], filter_by_admin: false, reassign_admin: false },
  employers: { create: false, export: false, filter_statuses: [], filter_by_admin: false, reassign_admin: false },
  admin_scopes: [],
  audit_logs: { view: false },
  academics: { view: false, manage: false },
};

/**
 * What the signed-in person may do, straight from the server. While it loads, nothing extra is shown;
 * screens stay usable because every request is authorised server-side anyway.
 */
export function usePermissions(): { permissions: Permissions; isLoading: boolean; can: (section: Section) => boolean; canOpen: (entry: MenuKey) => boolean } {
  const { data, isLoading, isFetching, isUninitialized } = useGetMyPermissionsQuery();
  const permissions = data ?? EMPTY;
  // Right after sign-in the first answer may still be on its way: wait for it rather than judge from nothing.
  const loading = !data && (isLoading || isFetching || isUninitialized);
  return { permissions, isLoading: loading, can: (section) => permissions.sections.includes(section), canOpen: (entry) => permissions.menu.includes(entry) };
}
