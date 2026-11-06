import type { EmploymentType, JobBase, LocationType } from "@/modules/job-portal/common/types";

export interface CandidateJob extends JobBase {
  eligibility_result: { eligible: boolean; reasons: string[] } | null;
  match: { score: number; explanation: string[]; breakdown: Record<string, unknown>; method: string } | null;
  applied: boolean;
  application_id: string | null;
}

export interface BoardFilters {
  q?: string;
  location?: string;
  employment_type?: EmploymentType;
  location_type?: LocationType;
  skill?: string;
  min_ctc?: number;
  eligible_only?: boolean;
  sort?: "relevance" | "newest" | "deadline" | "pay";
}

export interface JobPreferences {
  locations: string[];
  open_to_remote: boolean;
  roles: string[];
  min_ctc: number | null;
  employment_types: EmploymentType[];
  open_to_work: boolean;
}
