/** Form state for creating/editing a user. Field names match the API body so server errors map to fields. */
export interface GuardianFormValues {
  full_name: string;
  relationship: string;
  phone: string;
  email: string;
  occupation: string;
  is_primary: boolean;
}

export interface UserFormValues {
  role: string;
  organization_id: string;
  organization_label: string;
  manager_user_id: string;
  manager_label: string;
  /** Admins only; the form shows this section when the server says so. */
  scopes: string[];
  account: { email: string; username: string; set_password: boolean; password: string; generate_password?: boolean };
  personal_info: {
    first_name: string;
    middle_name: string;
    last_name: string;
    gender: string;
    date_of_birth: string;
    phone: string;
    alternate_phone: string;
    preferred_language: string;
    timezone: string;
  };
  include_address: boolean;
  address: { line1: string; line2: string; city: string; state: string; postal_code: string; country: string };
  employment: { employee_code: string; designation: string; department: string; employment_type: string; date_of_joining: string };
  student: {
    admission_number: string;
    admission_date: string;
    program: string;
    branch: string;
    year_of_study: string;
    section: string;
    graduation_year: string;
    cgpa: string;
    guardians: GuardianFormValues[];
  };
}
