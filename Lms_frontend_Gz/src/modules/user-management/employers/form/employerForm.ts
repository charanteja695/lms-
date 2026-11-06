import { compact, diffForUpdate } from "@/core/lib/query";
import type { Employer, EmployerBody } from "@/modules/user-management/employers/types";

/** Form state for creating/editing an employer. Field names match the API body. */
export interface EmployerFormValues {
  name: string;
  code: string;
  industry: string;
  admin_user_id: string;
  admin_label: string;
  contact: { email: string; phone: string; alternate_phone: string; website: string };
  address: { line1: string; line2: string; city: string; state: string; postal_code: string; country: string };
  timezone: string;
  registration_number: string;
  established_year: string;
}

export function emptyEmployerForm(): EmployerFormValues {
  return {
    name: "",
    code: "",
    industry: "",
    admin_user_id: "",
    admin_label: "",
    contact: { email: "", phone: "", alternate_phone: "", website: "" },
    address: { line1: "", line2: "", city: "", state: "", postal_code: "", country: "IN" },
    timezone: "",
    registration_number: "",
    established_year: "",
  };
}

export function employerToForm(employer: Employer): EmployerFormValues {
  const s = (value: string | number | null | undefined) => (value === null || value === undefined ? "" : String(value));
  return {
    name: employer.name,
    code: employer.code,
    industry: s(employer.industry),
    admin_user_id: employer.admin.user_id,
    admin_label: employer.admin.full_name,
    contact: {
      email: employer.contact.email,
      phone: employer.contact.phone,
      alternate_phone: s(employer.contact.alternate_phone),
      website: s(employer.contact.website),
    },
    address: { ...employer.address, line2: s(employer.address.line2) },
    timezone: employer.timezone,
    registration_number: s(employer.registration_number),
    established_year: s(employer.established_year),
  };
}

function shape(values: EmployerFormValues) {
  return {
    name: values.name,
    code: values.code.toUpperCase(),
    industry: values.industry,
    admin_user_id: values.admin_user_id,
    contact: values.contact,
    address: { ...values.address, country: values.address.country.toUpperCase() },
    timezone: values.timezone,
    registration_number: values.registration_number,
    established_year: values.established_year ? Number(values.established_year) : "",
  };
}

export function toEmployerCreateBody(values: EmployerFormValues): EmployerBody {
  return compact(shape(values)) as EmployerBody;
}

export function toEmployerUpdateBody(initial: EmployerFormValues, values: EmployerFormValues): EmployerBody {
  const before = shape(initial);
  const after = shape(values);
  const body = (diffForUpdate({ ...before, address: undefined }, { ...after, address: undefined }) ?? {}) as Record<string, unknown>;
  // The API replaces the whole address, so send it whole when anything in it changed.
  if (JSON.stringify(before.address) !== JSON.stringify(after.address)) body.address = compact(after.address);
  return body;
}

export function isEmployerField(field: string): boolean {
  return /^(name|code|industry|admin_user_id|timezone|registration_number|established_year|contact\.(email|phone|alternate_phone|website)|address\.(line1|line2|city|state|postal_code|country))$/.test(
    field,
  );
}
