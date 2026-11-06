import type { Id, IsoDateTime } from "@/core/api/types";

export interface Schedule {
  schedule_id: Id;
  test_id: Id;
  title: string | null;
  organization_id: Id | null;
  starts_at: IsoDateTime;
  ends_at: IsoDateTime;
  enforce_end: boolean;
  results_release_at: IsoDateTime | null;
  cancelled_at: IsoDateTime | null;
  created_at: IsoDateTime;
}

export interface ScheduleCreateBody {
  title?: string | null;
  organization_id?: string | null;
  starts_at: string;
  ends_at: string;
  enforce_end?: boolean;
  results_release_at?: string | null;
}

export interface ScheduleUpdateBody {
  title?: string | null;
  starts_at?: string;
  ends_at?: string;
  enforce_end?: boolean;
  results_release_at?: string | null;
}
