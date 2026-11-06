import { compact, diffForUpdate } from "@/core/lib/query";
import type { InstitutionFormValues } from "@/modules/user-management/institutions/form/institutionFormValues";
import type { Institution, InstitutionBody } from "@/modules/user-management/institutions/types";

export function emptyInstitutionForm(): InstitutionFormValues {
  return {
    name: "",
    code: "",
    type: "",
    admin_user_id: "",
    admin_label: "",
    contact: { email: "", phone: "", alternate_phone: "", website: "" },
    address: { line1: "", line2: "", city: "", state: "", postal_code: "", country: "IN" },
    timezone: "",
    registration_number: "",
    affiliation: "",
    established_year: "",
  };
}

export function institutionToForm(institution: Institution): InstitutionFormValues {
  const s = (value: string | null | undefined) => value ?? "";
  return {
    name: institution.name,
    code: institution.code,
    type: institution.type,
    admin_user_id: institution.admin.user_id,
    admin_label: institution.admin.full_name,
    contact: {
      email: institution.contact.email,
      phone: institution.contact.phone,
      alternate_phone: s(institution.contact.alternate_phone),
      website: s(institution.contact.website),
    },
    address: { ...institution.address, line2: s(institution.address.line2) },
    timezone: institution.timezone,
    registration_number: s(institution.registration_number),
    affiliation: s(institution.affiliation),
    established_year: institution.established_year ? String(institution.established_year) : "",
  };
}

function shape(values: InstitutionFormValues) {
  return {
    name: values.name,
    code: values.code.toUpperCase(),
    type: values.type,
    admin_user_id: values.admin_user_id,
    contact: values.contact,
    address: { ...values.address, country: values.address.country.toUpperCase() },
    timezone: values.timezone,
    registration_number: values.registration_number,
    affiliation: values.affiliation,
    established_year: values.established_year ? Number(values.established_year) : "",
  };
}

export function toInstitutionCreateBody(values: InstitutionFormValues): InstitutionBody {
  return compact(shape(values)) as InstitutionBody;
}

export function toInstitutionUpdateBody(initial: InstitutionFormValues, values: InstitutionFormValues): InstitutionBody {
  const before = shape(initial);
  const after = shape(values);
  const body = (diffForUpdate({ ...before, address: undefined }, { ...after, address: undefined }) ?? {}) as Record<string, unknown>;
  // The API replaces the whole address, so send it whole when anything in it changed.
  if (JSON.stringify(before.address) !== JSON.stringify(after.address)) body.address = compact(after.address);
  return body;
}

export function isInstitutionField(field: string): boolean {
  return /^(name|code|type|admin_user_id|timezone|registration_number|affiliation|established_year|contact\.(email|phone|alternate_phone|website)|address\.(line1|line2|city|state|postal_code|country))$/.test(field);
}
