import { Id, IsoDate, IsoDateTime, SortOrder } from "@/core/api/types";
import {
  Address,
  AdminScope,
  InstitutionRef,
  ManagedRole,
  Role,
  UserAction,
  UserRef,
  UserStatus,
} from "@/modules/user-management/common/types";

export type Gender = "male" | "female" | "other" | "prefer_not_to_say";

export type GuardianRelationship = "father" | "mother" | "legal_guardian" | "grandparent" | "sibling" | "other";

export type EmploymentType = "full_time" | "part_time" | "contract" | "visiting" | "intern";

export type UserSortColumn = "created_time" | "first_name" | "last_name" | "email" | "last_login_time";

export type ImportMode = "all_or_nothing" | "skip_invalid";

export interface Guardian {
  full_name: string;
  relationship: GuardianRelationship;
  phone: string;
  email: string | null;
  occupation: string | null;
  is_primary: boolean;
}

/** Academic placement, used by batches, reports and job eligibility. */
export interface StudentProfile {
  admission_number: string;
  admission_date: IsoDate | null;
  program: string | null;
  branch: string | null;
  year_of_study: number | null;
  section: string | null;
  graduation_year: number | null;
  cgpa: string | null;
  guardians: Guardian[];
}

export interface User {
  user_id: Id;
  role: Role;
  status: UserStatus;
  status_reason: string | null;
  account: {
    email: string | null;
    username: string;
    email_verified: boolean;
    must_change_password: boolean;
    last_login_time: IsoDateTime | null;
    password_changed_time: IsoDateTime | null;
  };
  personal_info: {
    first_name: string;
    middle_name: string | null;
    last_name: string;
    full_name: string;
    gender: Gender | null;
    date_of_birth: IsoDate | null;
    phone: string | null;
    alternate_phone: string | null;
    preferred_language: string;
    timezone: string;
  };
  address: Address | null;
  employment: {
    employee_code: string | null;
    designation: string | null;
    department: string | null;
    employment_type: EmploymentType | null;
    date_of_joining: IsoDate | null;
  } | null;
  student: StudentProfile | null;
  institution: InstitutionRef | null;
  manager: UserRef | null;
  created_by: UserRef | null;
  /** Admins only: their platform responsibilities. */
  scopes: AdminScope[];
  created_time: IsoDateTime;
  modified_time: IsoDateTime;
  deleted_time: IsoDateTime | null;
  /** What the viewer may do with this record. The UI renders these; the server enforces them. */
  allowed_actions: UserAction[];
}

export interface Admin extends User {
  institution_count: number;
  employer_count: number;
}

export interface UserListItem {
  user_id: Id;
  role: Role;
  status: UserStatus;
  full_name: string;
  email: string | null;
  username: string;
  phone: string | null;
  employee_code: string | null;
  admission_number: string | null;
  branch: string | null;
  year_of_study: number | null;
  section: string | null;
  graduation_year: number | null;
  cgpa: string | null;
  institution: InstitutionRef | null;
  last_login_time: IsoDateTime | null;
  created_time: IsoDateTime;
  allowed_actions: UserAction[];
}

export interface AdminListItem extends UserListItem {
  institution_count: number;
  employer_count: number;
  scopes: AdminScope[];
}

export interface UserFilters {
  search_text?: string;
  role?: ManagedRole;
  status?: UserStatus;
  organization_id?: Id;
  manager_user_id?: Id;
  created_by_user_id?: Id;
  gender?: Gender;
  department?: string;
  employment_type?: EmploymentType;
  email_verified?: boolean;
  program?: string;
  branch?: string;
  section?: string;
  year_of_study?: number;
  graduation_year?: number;
  scope?: AdminScope;
  created_from?: IsoDate;
  created_to?: IsoDate;
  sort_column?: UserSortColumn;
  sort_order?: SortOrder;
}

/** Request body for POST /users. Optional sections are omitted rather than sent empty. */
export interface UserCreateBody {
  role: ManagedRole;
  organization_id?: Id;
  manager_user_id?: Id;
  account: { email?: string; username?: string; password?: string; generate_password?: boolean };
  scopes?: AdminScope[];
  personal_info: {
    first_name: string;
    middle_name?: string;
    last_name: string;
    gender?: Gender;
    date_of_birth?: IsoDate;
    phone?: string;
    alternate_phone?: string;
    preferred_language?: string;
    timezone?: string;
  };
  address?: Omit<Address, "line2"> & { line2?: string };
  employment?: Partial<NonNullable<User["employment"]>>;
  student?: {
    admission_number: string;
    admission_date?: IsoDate;
    program?: string;
    branch?: string;
    year_of_study?: number;
    section?: string;
    graduation_year?: number;
    cgpa?: string;
    guardians?: Array<Omit<Guardian, "email" | "occupation"> & { email?: string; occupation?: string }>;
  };
}

/** How a new user gets access. A temporary password is shown only in the create response. */
export interface Credentials {
  delivery: "email_link" | "initial_password" | "temporary_password";
  temporary_password: string | null;
  email_sent?: boolean | null;
  setup_link?: string | null;
  message?: string | null;
}

export interface CreatedUser {
  user: User;
  credentials: Credentials;
}

/** Partial update: only changed fields are sent; null clears an optional value. */
export type UserUpdateBody = Record<string, unknown>;

export interface ImportResult {
  dry_run: boolean;
  mode: ImportMode;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  created: number;
  created_users: Array<{ row: number; user_id: Id; email: string | null; username: string; temporary_password: string | null }>;
  errors: Array<{ row: number; column: string | null; code: string; message: string }>;
}
