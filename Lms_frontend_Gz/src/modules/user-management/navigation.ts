import type { NavItem } from "@/app/navigation";

export const employersNavigation: NavItem[] = [
  { section: "employers", label: "Hiring Companies", icon: "briefcase", to: "/employers", group: "careers", hint: "" },
];

/**
 * One entry per menu section the server can return in `permissions.sections`. My profile and Security live in the
 * header's account menu, not the sidebar.
 * The server decides who sees what; this only gives each section a label, icon and path.
 */
export const userManagementNavigation: NavItem[] = [
  // User management: the people who use the platform, top to bottom of the hierarchy
  { section: "admins", label: "Admins", icon: "shield", to: "/admins", group: "users", hint: "" },
  { section: "institutions", label: "Institutions", icon: "building", to: "/institutions", group: "users", hint: "" },
  { section: "users", viewRole: "institution_head", label: "Institution heads", icon: "user", to: "/institution-heads", group: "users", hint: "" },
  { section: "users", viewRole: "staff", label: "Staff", icon: "briefcase", to: "/staff", group: "users", hint: "" },
  { section: "users", viewRole: "student", label: "Students", icon: "graduation", to: "/students", group: "users", hint: "" },
  { section: "hierarchy", label: "Organisation hierarchy", icon: "layers", to: "/organisation", group: "admin", hint: "" },
  { section: "permissions", label: "Roles & permissions", icon: "key", to: "/permissions", group: "admin", hint: "" },
  { section: "my_organization", label: "My organisation", icon: "building", to: "/my-organization", group: "academics", hint: "" },
  { section: "academics", label: "Academic structure", icon: "layers", to: "/academics", group: "academics", hint: "" },
  { section: "academics", label: "Marks & results", icon: "chart", to: "/results", group: "academics", hint: "" },
  { section: "downloads", label: "Data exports", icon: "download", to: "/downloads", group: "admin", hint: "" },
  { section: "audit_logs", label: "System audit log", icon: "search", to: "/audit-logs", group: "admin", hint: "" },
];
