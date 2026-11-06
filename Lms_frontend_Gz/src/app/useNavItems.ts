import { NAVIGATION, type NavItem } from "@/app/navigation";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";

/** The navigation entries the server lets this person open (feature-level `menu`, user-management's `sections`, or the roles it may see). */
export function useNavItems(): NavItem[] {
  const { can, canOpen, permissions } = usePermissions();
  return NAVIGATION.filter((i) => {
    if (i.viewRole) return permissions.users.view_roles.includes(i.viewRole);
    return i.menu ? canOpen(i.menu) : can(i.section);
  });
}
