import type { AdminScope, ManagedRole, OrganizationType, Role, UserStatus } from "@/modules/user-management/common/types";

/** Menu sections the signed-in person may open, as returned by GET /users/me/permissions. */
export type Section =
  | "dashboard"
  | "admins"
  | "institutions"
  | "employers"
  | "my_organization"
  | "users"
  | "downloads"
  | "audit_logs"
  | "academics"
  | "hierarchy"
  | "permissions"
  | "profile"
  | "security"
  // One per other backend service (docs/PRODUCT.md §6); see user-management's capabilities.py for who gets which.
  | "store"
  | "catalog"
  | "subscriptions"
  | "learning"
  | "code_execution"
  | "assessments"
  | "proctoring"
  | "certificates"
  | "ai_tutor"
  | "support"
  | "career"
  | "job_portal"
  | "ai_interview"
  | "notifications"
  | "analytics"
  | "billing"
  | "ai_gateway";

/** Entries inside those modules (feature level), from user-management's `_MENU_ACCESS`: which screens a role or scope gets. */
export type MenuKey =
  | "my_learning"
  | "batches"
  | "courses"
  | "learning_paths"
  | "media_library"
  | "store"
  | "course_requests"
  | "subscriptions"
  | "problems"
  | "compiler"
  | "my_submissions"
  | "ai_tutor"
  | "my_tests"
  | "question_bank"
  | "tests"
  | "attempts"
  | "grading"
  | "my_integrity_cases"
  | "proctoring"
  | "certificates"
  | "support"
  | "career"
  | "jobs"
  | "ai_interviews"
  | "analytics"
  | "billing"
  | "ai_settings";

export interface OrganizationPermissions {
  create: boolean;
  /** May download the list. */
  export: boolean;
  filter_statuses: UserStatus[];
  filter_by_admin: boolean;
  reassign_admin: boolean;
}

export interface Permissions {
  role: Role;
  organization_type: OrganizationType | null;
  scopes: AdminScope[];
  /** Effective permissions: matrix cells (`students.delete`), the feature keys they imply, and an admin's scopes. */
  permissions: string[];
  sections: Section[];
  menu: MenuKey[];
  users: {
    view_roles: ManagedRole[];
    create_roles: ManagedRole[];
    can_import: boolean;
    can_export: boolean;
    filter_statuses: UserStatus[];
    filter_by_institution: boolean;
  };
  admins: { view: boolean; create: boolean };
  institutions: OrganizationPermissions;
  employers: OrganizationPermissions;
  admin_scopes: AdminScope[];
  audit_logs: { view: boolean };
  academics: { view: boolean; manage: boolean };
}

/** Description of the create/edit user form for one role, from GET /users/form-options. */
export interface UserFormOptions {
  roles: ManagedRole[];
  role_editable: boolean;
  organization: { shown: boolean; type: OrganizationType | null; required: boolean; selectable: boolean; fixed: boolean };
  scopes: { shown: boolean; options: AdminScope[]; default: AdminScope[] };
  manager: { shown: boolean; role: Role | null; defaults_to_you: boolean };
  sections: { address: boolean; employment: boolean; student: boolean; guardians: boolean };
  guardians: { max: number; required_below_age: number };
  initial_password: { allowed: boolean; min_length: number; generated_without_email: boolean };
  email_optional: boolean;
  required_fields: string[];
  defaults: { language: string; timezone: string; country: string };
}
