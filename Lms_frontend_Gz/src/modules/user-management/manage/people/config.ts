import type { ManagedRole } from "@/modules/user-management/common/types";
import type { UserResource } from "@/modules/user-management/users/api/usersApi";

/** The four people screens of User management. Admins live under /admins; the others are users of one role. */
export type PersonKind = Extract<ManagedRole, "admin" | "institution_head" | "staff" | "student">;

export interface PersonScreen {
  resource: UserResource;
  title: string;
  /** Singular, lower case: "Add staff member", "Edit staff member". */
  one: string;
  description: string;
  searchPlaceholder: string;
  /** Under the form title when adding. */
  addHint: string;
}

const EMAIL_SETUP = "They get an email with a link to set their password.";

export const PERSON_SCREENS: Record<PersonKind, PersonScreen> = {
  admin: {
    resource: "admins",
    title: "Admins",
    one: "admin",
    description: "Admins own institutions and look after the people in them.",
    searchPlaceholder: "Search by name or email",
    addHint: EMAIL_SETUP,
  },
  institution_head: {
    resource: "users",
    title: "Institution heads",
    one: "institution head",
    description: "The person who runs an institution and manages its staff and students.",
    searchPlaceholder: "Search by name, email or employee code",
    addHint: EMAIL_SETUP,
  },
  staff: {
    resource: "users",
    title: "Staff",
    one: "staff member",
    description: "Teachers and staff who teach and guide students.",
    searchPlaceholder: "Search by name, email or employee code",
    addHint: EMAIL_SETUP,
  },
  student: {
    resource: "users",
    title: "Students",
    one: "student",
    description: "Learners who take courses and tests.",
    searchPlaceholder: "Search by name, email or admission number",
    addHint: "With an email they get a link to set their password; without one, you get a one-time password to give them.",
  },
};

export const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
