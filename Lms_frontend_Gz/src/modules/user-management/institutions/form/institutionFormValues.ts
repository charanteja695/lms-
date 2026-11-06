/** Form state for creating/editing an institution. Field names match the API body. */
export interface InstitutionFormValues {
  name: string;
  code: string;
  type: string;
  admin_user_id: string;
  admin_label: string;
  contact: { email: string; phone: string; alternate_phone: string; website: string };
  address: { line1: string; line2: string; city: string; state: string; postal_code: string; country: string };
  timezone: string;
  registration_number: string;
  affiliation: string;
  established_year: string;
}
