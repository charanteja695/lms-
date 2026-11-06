import type { Id, IsoDateTime } from "@/core/api/types";
import type { SessionStatus } from "@/modules/proctoring/common/types";

export interface MonitorSession {
  session_id: Id;
  test_id: Id;
  test_title: string | null;
  user_id: Id;
  organization_id: Id | null;
  attempt_id: Id | null;
  level: string;
  status: SessionStatus;
  started_at: IsoDateTime | null;
  ended_at: IsoDateTime | null;
  last_heartbeat_at: IsoDateTime | null;
  risk_score: number;
  critical: boolean;
  terminated: boolean;
  created_at: IsoDateTime;
}

export interface MonitorSessionDetail extends MonitorSession {
  risk_breakdown: Record<string, number>;
  heartbeat_lost: boolean;
  consent_version: string | null;
  ip_address: string | null;
}

export interface Directive {
  kind: string;
  message: string | null;
  created_at: IsoDateTime;
}

export interface MonitorFilters {
  test_id?: string;
  status?: SessionStatus;
  min_risk?: number;
  only_critical?: boolean;
}
