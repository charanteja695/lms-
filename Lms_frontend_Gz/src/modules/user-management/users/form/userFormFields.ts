export const FORM_FIELDS = new Set<string>([
  "role",
  "organization_id",
  "manager_user_id",
  "account.email",
  "account.username",
  "account.password",
  ...["first_name", "middle_name", "last_name", "gender", "date_of_birth", "phone", "alternate_phone", "preferred_language", "timezone"].map((f) => `personal_info.${f}`),
  ...["line1", "line2", "city", "state", "postal_code", "country"].map((f) => `address.${f}`),
  ...["employee_code", "designation", "department", "employment_type", "date_of_joining"].map((f) => `employment.${f}`),
  "student.admission_number",
  "student.admission_date",
  "student.guardians",
]);

export function isFormField(field: string): boolean {
  return FORM_FIELDS.has(field) || /^student\.guardians\.\d+\.(full_name|relationship|phone|email|occupation)$/.test(field);
}
