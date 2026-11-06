import type { AdminScope, OrganizationType, Role, UserStatus } from "@/modules/user-management/common/types";
import type { InstitutionType } from "@/modules/user-management/institutions/types";
import type { EmploymentType, Gender, GuardianRelationship } from "@/modules/user-management/users/types";
import type { BadgeTone } from "@/shared/ui";

export const ROLE_LABELS: Record<Role, string> = {
  super_admin: "Super admin",
  admin: "Admin",
  institution_head: "Institution head",
  staff: "Staff",
  student: "Student",
  employer_admin: "Employer admin",
  recruiter: "Recruiter",
};

export const ROLE_TONES: Record<Role, BadgeTone> = {
  super_admin: "purple",
  admin: "indigo",
  institution_head: "blue",
  staff: "amber",
  student: "gray",
  employer_admin: "blue",
  recruiter: "amber",
};

export const STATUS_LABELS: Record<UserStatus, string> = { active: "Active", suspended: "Suspended", deleted: "Deleted" };

export const STATUS_TONES: Record<UserStatus, BadgeTone> = { active: "green", suspended: "amber", deleted: "red" };

export const GENDER_LABELS: Record<Gender, string> = {
  male: "Male",
  female: "Female",
  other: "Other",
  prefer_not_to_say: "Prefer not to say",
};

export const RELATIONSHIP_LABELS: Record<GuardianRelationship, string> = {
  father: "Father",
  mother: "Mother",
  legal_guardian: "Legal guardian",
  grandparent: "Grandparent",
  sibling: "Sibling",
  other: "Other",
};

export const EMPLOYMENT_TYPE_LABELS: Record<EmploymentType, string> = {
  full_time: "Full time",
  part_time: "Part time",
  contract: "Contract",
  visiting: "Visiting",
  intern: "Intern",
};

export const ADMIN_SCOPE_LABELS: Record<AdminScope, string> = {
  "accounts.manage": "Institutions and their members",
  "careers.manage": "Companies, jobs and hiring",
  "content.author": "Write courses",
  "content.review": "Review and publish courses",
  "exams.manage": "Exams and integrity reviews",
  "support.manage": "Support tickets",
  "ai.manage": "AI settings",
  "analytics.view": "Platform-wide analytics",
  "billing.manage": "Billing: quotes, invoices and payments",
};

export const ORGANIZATION_LABELS: Record<OrganizationType, { one: string; many: string; path: string }> = {
  institution: { one: "Institution", many: "Institutions", path: "/institutions" },
  employer: { one: "Company", many: "Companies", path: "/employers" },
};

export const INSTITUTION_TYPE_LABELS: Record<InstitutionType, string> = {
  school: "School",
  college: "College",
  university: "University",
  coaching_center: "Coaching center",
  training_institute: "Training institute",
  other: "Other",
};
