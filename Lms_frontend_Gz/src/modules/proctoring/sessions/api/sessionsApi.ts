import { baseApi } from "@/core/api/baseApi";
import type { PrecheckBody, PrecheckResult, ProctorSession, RegisteredSnapshot, Requirements, UploadTarget } from "@/modules/proctoring/sessions/types";

export const sessionsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    createProctorSession: build.mutation<{ session: ProctorSession; requirements: Requirements }, string>({
      query: (testId) => ({ url: "/sessions", method: "POST", body: { test_id: testId } }),
      invalidatesTags: ["ProctorSession"],
    }),
    getProctorSnapshotUploadUrl: build.mutation<UploadTarget, { sessionId: string; kind: string; contentType?: string; pose?: string }>({
      query: ({ sessionId, kind, contentType, pose }) => ({
        url: `/sessions/${sessionId}/snapshots/upload-url`,
        method: "POST",
        body: { kind, content_type: contentType, pose },
      }),
      transformResponse: (response: { file: UploadTarget }) => response.file,
    }),
    registerProctorSnapshot: build.mutation<RegisteredSnapshot, { sessionId: string; kind: string; key: string }>({
      query: ({ sessionId, kind, key }) => ({ url: `/sessions/${sessionId}/snapshots`, method: "POST", body: { kind, key } }),
      transformResponse: (response: { snapshot: RegisteredSnapshot }) => response.snapshot,
    }),
    submitPrecheck: build.mutation<PrecheckResult, { sessionId: string; body: PrecheckBody }>({
      query: ({ sessionId, body }) => ({ url: `/sessions/${sessionId}/precheck`, method: "POST", body }),
      invalidatesTags: ["ProctorSession"],
    }),
  }),
});

export const {
  useCreateProctorSessionMutation,
  useGetProctorSnapshotUploadUrlMutation,
  useRegisterProctorSnapshotMutation,
  useSubmitPrecheckMutation,
} = sessionsApi;
