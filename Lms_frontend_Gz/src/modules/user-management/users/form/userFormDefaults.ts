import type { UserFormValues } from "@/modules/user-management/users/form/userFormValues";
import type { User } from "@/modules/user-management/users/types";

export const emptyGuardian = (isPrimary: boolean): UserFormValues["student"]["guardians"][number] => ({
  full_name: "",
  relationship: "",
  phone: "",
  email: "",
  occupation: "",
  is_primary: isPrimary,
});

export function emptyUserForm(defaults: Partial<Pick<UserFormValues, "role" | "organization_id" | "organization_label">> = {}): UserFormValues {
  return {
    role: defaults.role ?? "",
    organization_id: defaults.organization_id ?? "",
    organization_label: defaults.organization_label ?? "",
    manager_user_id: "",
    manager_label: "",
    scopes: [],
    account: { email: "", username: "", set_password: false, password: "", generate_password: false },
    personal_info: {
      first_name: "",
      middle_name: "",
      last_name: "",
      gender: "",
      date_of_birth: "",
      phone: "",
      alternate_phone: "",
      preferred_language: "",
      timezone: "",
    },
    include_address: false,
    address: { line1: "", line2: "", city: "", state: "", postal_code: "", country: "IN" },
    employment: { employee_code: "", designation: "", department: "", employment_type: "", date_of_joining: "" },
    student: {
      admission_number: "",
      admission_date: "",
      program: "",
      branch: "",
      year_of_study: "",
      section: "",
      graduation_year: "",
      cgpa: "",
      guardians: [],
    },
  };
}

/** Populate the form from an existing user (edit mode). */
export function userToForm(user: User): UserFormValues {
  const base = emptyUserForm();
  const s = (value: string | number | null | undefined) => (value === null || value === undefined ? "" : String(value));
  return {
    ...base,
    role: user.role === "super_admin" ? "" : user.role,
    organization_id: user.institution?.organization_id ?? "",
    organization_label: user.institution?.name ?? "",
    manager_user_id: user.manager?.user_id ?? "",
    manager_label: user.manager?.full_name ?? "",
    scopes: [...user.scopes],
    account: { email: s(user.account.email), username: user.account.username, set_password: false, password: "" },
    personal_info: {
      first_name: user.personal_info.first_name,
      middle_name: s(user.personal_info.middle_name),
      last_name: user.personal_info.last_name,
      gender: s(user.personal_info.gender),
      date_of_birth: s(user.personal_info.date_of_birth),
      phone: s(user.personal_info.phone),
      alternate_phone: s(user.personal_info.alternate_phone),
      preferred_language: user.personal_info.preferred_language,
      timezone: user.personal_info.timezone,
    },
    include_address: Boolean(user.address),
    address: user.address
      ? {
          line1: user.address.line1,
          line2: s(user.address.line2),
          city: user.address.city,
          state: user.address.state,
          postal_code: user.address.postal_code,
          country: user.address.country,
        }
      : base.address,
    employment: {
      employee_code: s(user.employment?.employee_code),
      designation: s(user.employment?.designation),
      department: s(user.employment?.department),
      employment_type: s(user.employment?.employment_type),
      date_of_joining: s(user.employment?.date_of_joining),
    },
    student: {
      admission_number: s(user.student?.admission_number),
      admission_date: s(user.student?.admission_date),
      program: s(user.student?.program),
      branch: s(user.student?.branch),
      year_of_study: s(user.student?.year_of_study),
      section: s(user.student?.section),
      graduation_year: s(user.student?.graduation_year),
      cgpa: s(user.student?.cgpa),
      guardians: (user.student?.guardians ?? []).map((guardian) => ({
        full_name: guardian.full_name,
        relationship: guardian.relationship,
        phone: guardian.phone,
        email: s(guardian.email),
        occupation: s(guardian.occupation),
        is_primary: guardian.is_primary,
      })),
    },
  };
}
