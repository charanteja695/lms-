import { Id, IsoDateTime, SortOrder } from "@/core/api/types";
import { Address, InstitutionStatus, OrganizationAction, UserRef } from "@/modules/user-management/common/types";

export type EmployerSortColumn = "created_time" | "name" | "code";

export interface EmployerMemberCounts {
  employer_admins: number;
  recruiters: number;
  total: number;
}

export interface Employer {
  organization_id: Id;
  name: string;
  code: string;
  industry: string | null;
  status: InstitutionStatus;
  status_reason: string | null;
  contact: { email: string; phone: string; alternate_phone: string | null; website: string | null };
  address: Address;
  timezone: string;
  registration_number: string | null;
  established_year: number | null;
  admin: UserRef;
  member_counts: EmployerMemberCounts;
  created_by: UserRef | null;
  created_time: IsoDateTime;
  modified_time: IsoDateTime;
  deleted_time: IsoDateTime | null;
  allowed_actions: OrganizationAction[];
}

export interface EmployerListItem {
  organization_id: Id;
  name: string;
  code: string;
  industry: string | null;
  status: InstitutionStatus;
  city: string;
  state: string;
  country: string;
  admin: UserRef;
  member_counts: EmployerMemberCounts;
  created_time: IsoDateTime;
  allowed_actions: OrganizationAction[];
}

export interface EmployerFilters {
  search_text?: string;
  status?: InstitutionStatus;
  industry?: string;
  admin_user_id?: Id;
  country?: string;
  state?: string;
  city?: string;
  created_from?: string;
  created_to?: string;
  sort_column?: EmployerSortColumn;
  sort_order?: SortOrder;
}

/** Only changed fields are sent, so the body is built from the form. */
export type EmployerBody = Record<string, unknown>;
