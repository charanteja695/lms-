import type { Id, IsoDateTime } from "@/core/api/types";
import type { LivenessPose, SessionStatus, SnapshotKind } from "@/modules/proctoring/common/types";

export interface Requirements {
  level: string;
  consent_version: string;
  needs: string[];
  snapshot_interval_seconds: number;
  heartbeat_interval_seconds: number;
  min_bandwidth_kbps: number;
  /** strict, if the test requires it: share the entire screen for the whole test */
  screen_share: boolean;
  /** strict: a microphone clip this often (0 = never), this long */
  audio_interval_seconds: number;
  audio_clip_seconds: number;
  /** strict: turn the face each way before the test, one frame per pose */
  liveness_poses: LivenessPose[];
  /** strict: the whole test is recorded (camera + microphone) in pieces of this many seconds */
  video_recording: boolean;
  video_chunk_seconds: number;
}

export interface ProctorSession {
  session_id: Id;
  test_id: Id;
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

export interface PrecheckBody {
  consent: boolean;
  consent_version: string;
  browser: string;
  fullscreen_supported: boolean;
  camera?: boolean;
  microphone?: boolean;
  bandwidth_kbps?: number;
  screen_share?: boolean;
  device_fingerprint?: string | null;
}

export interface PrecheckResult {
  ready: boolean;
  failures: Record<string, string>[];
  session: ProctorSession;
}

export interface UploadTarget {
  key: string;
  upload: { url: string; fields: Record<string, string> };
  expires_in: number;
}

export interface RegisteredSnapshot {
  snapshot_id: Id;
  kind: SnapshotKind;
  sequence: number;
  taken_at: IsoDateTime;
  analysis_status: string;
}
