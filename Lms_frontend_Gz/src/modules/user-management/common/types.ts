import { Id } from "@/core/api/types";

export type Role = "super_admin" | "admin" | "institution_head" | "staff" | "student" | "employer_admin" | "recruiter";

export type ManagedRole = Exclude<Role, "super_admin">;

export type UserStatus = "active" | "suspended" | "deleted";

export type InstitutionStatus = UserStatus;

export type StatusChange = "active" | "suspended";

/** Institutions and employers are both organisations, addressed by organization_id. */
export type OrganizationType = "institution" | "employer";

export type AdminScope =
  | "accounts.manage"
  | "careers.manage"
  | "content.author"
  | "content.review"
  | "exams.manage"
  | "support.manage"
  | "ai.manage"
  | "analytics.view"
  | "billing.manage";

/** Values of `allowed_actions` on users and organisations. The server decides; the UI only renders them. */
export type UserAction = "update" | "suspend" | "activate" | "revoke_sessions" | "reset_mfa" | "set_password" | "delete";
export type OrganizationAction = "update" | "suspend" | "activate" | "revoke_sessions" | "delete" | "add_member" | "view_members";

export interface UserRef {
  user_id: Id;
  full_name: string;
  role: Role;
  email: string | null;
}

export interface InstitutionRef {
  organization_id: Id;
  name: string;
  code: string;
  organization_type: OrganizationType;
}

export interface Address {
  line1: string;
  line2: string | null;
  city: string;
  state: string;
  postal_code: string;
  country: string;
}
