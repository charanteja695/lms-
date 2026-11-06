import { baseApi } from "@/core/api/baseApi";

export interface ProctorDirective {
  kind: string;
  message: string | null;
  created_at: string;
}

export interface ProctorHeartbeatResult {
  session_status: string;
  risk_score: number;
  directives: ProctorDirective[];
  snapshot_interval_seconds: number;
  server_time: string;
}

export interface ProctorEventInput {
  type: string;
  occurred_at?: string;
  detail?: Record<string, unknown>;
}

/**
 * The exam player's own calls to proctoring-service (heartbeat, events, periodic snapshots) — a
 * separate endpoint definition in this module's `api/`, not an import of the proctoring module's,
 * per rule 5 (only narrow id->name resolvers cross a module boundary; this is a whole client).
 */
export const proctoringClientApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    sendProctorHeartbeat: build.mutation<ProctorHeartbeatResult, { sessionId: string }>({
      query: ({ sessionId }) => ({ url: `/sessions/${sessionId}/heartbeat`, method: "POST", body: {} }),
    }),
    reportProctorEvents: build.mutation<{ accepted: number; risk_score: number }, { sessionId: string; events: ProctorEventInput[] }>({
      query: ({ sessionId, events }) => ({ url: `/sessions/${sessionId}/events`, method: "POST", body: { events } }),
    }),
    getExamSnapshotUploadUrl: build.mutation<{ key: string; upload: { url: string; fields: Record<string, string> } }, { sessionId: string; kind: string; contentType?: string }>({
      query: ({ sessionId, kind, contentType = "image/jpeg" }) => ({ url: `/sessions/${sessionId}/snapshots/upload-url`, method: "POST", body: { kind, content_type: contentType } }),
      transformResponse: (response: { file: { key: string; upload: { url: string; fields: Record<string, string> } } }) => response.file,
    }),
    registerExamSnapshot: build.mutation<void, { sessionId: string; kind: string; key: string }>({
      query: ({ sessionId, kind, key }) => ({ url: `/sessions/${sessionId}/snapshots`, method: "POST", body: { kind, key } }),
    }),
  }),
});

export const {
  useSendProctorHeartbeatMutation,
  useReportProctorEventsMutation,
  useGetExamSnapshotUploadUrlMutation,
  useRegisterExamSnapshotMutation,
} = proctoringClientApi;
