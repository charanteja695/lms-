/**
 * API contract types. They mirror lms-backend/user-management/docs/API.md exactly.
 * All ids are strings (64-bit numbers); timestamps are UTC ISO strings; dates are YYYY-MM-DD.
 */
export type Id = string;

export type IsoDateTime = string;

export type IsoDate = string;

export type SortOrder = "asc" | "desc";

export interface SuccessEnvelope {
  status: "success";
  code: string;
  message: string;
}

export interface PageContext {
  page: number;
  per_page: number;
  total_records: number;
  total_is_exact: boolean;
  total_pages: number;
  has_more_page: boolean;
  sort_column: string;
  sort_order: SortOrder;
}

export interface ErrorDetail {
  field: string | null;
  code: string;
  message: string;
}

export interface ApiErrorBody {
  status: "error";
  code: string;
  message: string;
  details: ErrorDetail[];
  request_id: string | null;
}

export interface PageParams {
  page?: number;
  per_page?: number;
}

export interface ListResult<T> {
  items: T[];
  pageContext: PageContext;
}
