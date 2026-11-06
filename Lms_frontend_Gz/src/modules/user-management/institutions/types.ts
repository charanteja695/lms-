import { Id, IsoDate, IsoDateTime, SortOrder } from "@/core/api/types";
import { Address, InstitutionStatus, OrganizationAction, UserRef } from "@/modules/user-management/common/types";

export type InstitutionType = "school" | "college" | "university" | "coaching_center" | "training_institute" | "other";

export type InstitutionSortColumn = "created_time" | "name" | "code";

export interface Institution {
  organization_id: Id;
  name: string;
  code: string;
  type: InstitutionType;
  status: InstitutionStatus;
  status_reason: string | null;
  contact: { email: string; phone: string; alternate_phone: string | null; website: string | null };
  address: Address;
  timezone: string;
  registration_number: string | null;
  affiliation: string | null;
  established_year: number | null;
  admin: UserRef;
  member_counts: { institution_heads: number; staff: number; students: number; total: number };
  created_by: UserRef | null;
  created_time: IsoDateTime;
  modified_time: IsoDateTime;
  deleted_time: IsoDateTime | null;
  allowed_actions: OrganizationAction[];
}

export interface InstitutionListItem {
  organization_id: Id;
  name: string;
  code: string;
  type: InstitutionType;
  status: InstitutionStatus;
  city: string;
  state: string;
  country: string;
  admin: UserRef;
  member_counts: Institution["member_counts"];
  created_time: IsoDateTime;
  allowed_actions: OrganizationAction[];
}

export interface InstitutionFilters {
  search_text?: string;
  status?: InstitutionStatus;
  type?: InstitutionType;
  admin_user_id?: Id;
  country?: string;
  state?: string;
  city?: string;
  affiliation?: string;
  created_from?: IsoDate;
  created_to?: IsoDate;
  sort_column?: InstitutionSortColumn;
  sort_order?: SortOrder;
}

export type InstitutionBody = Record<string, unknown>;
