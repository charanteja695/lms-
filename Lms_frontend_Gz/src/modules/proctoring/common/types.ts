/** Mirrors proctoring-service's enums (see docs/API.md). */
export type SessionStatus = "precheck" | "ready" | "active" | "submitted" | "closed" | "superseded" | "abandoned";

export type CaseStatus = "open" | "under_review" | "decided" | "appealed" | "final";

export type CaseSeverity = "low" | "medium" | "high";

export type SnapshotKind = "id_photo" | "face_enrol" | "liveness" | "periodic" | "screen" | "audio" | "video";

export type LivenessPose = "left" | "right" | "up" | "down";

export type AnalysisStatus = "pending" | "complete" | "partial" | "unavailable" | "not_applicable" | "skipped";

export type CaseDecision = "reviewed_ok" | "invalidated";

export type AppealOutcome = "upheld" | "overturned";

/** Event types a client may report (docs/API.md); each adds weighted risk, capped per type. */
export const BASIC_EVENT_TYPES = [
  "fullscreen_exit", "tab_switch", "window_blur", "copy_paste", "right_click", "devtools_open", "multiple_monitors", "network_lost",
] as const;

export const STRICT_EVENT_TYPES = ["camera_off", "mic_off", "screen_share_stopped"] as const;

export type ClientEventType = (typeof BASIC_EVENT_TYPES)[number] | (typeof STRICT_EVENT_TYPES)[number];
