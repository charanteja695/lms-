import type { User } from "@/modules/user-management/users/types";

/** Contact details a person may edit on their own profile. */
export interface ContactFormValues {
  personal_info: { phone: string; alternate_phone: string; preferred_language: string; timezone: string };
  include_address: boolean;
  address: { line1: string; line2: string; city: string; state: string; postal_code: string; country: string };
}

export function toContactFormValues(user: User): ContactFormValues {
  return {
    personal_info: {
      phone: user.personal_info.phone ?? "",
      alternate_phone: user.personal_info.alternate_phone ?? "",
      preferred_language: user.personal_info.preferred_language,
      timezone: user.personal_info.timezone,
    },
    include_address: Boolean(user.address),
    address: user.address ? { ...user.address, line2: user.address.line2 ?? "" } : { line1: "", line2: "", city: "", state: "", postal_code: "", country: "IN" },
  };
}
