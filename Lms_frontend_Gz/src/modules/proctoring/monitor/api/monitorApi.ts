import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { Directive, MonitorFilters, MonitorSession, MonitorSessionDetail } from "@/modules/proctoring/monitor/types";

export const monitorApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listMonitorSessions: build.query<ListResult<MonitorSession>, MonitorFilters & PageParams>({
      query: (params) => ({ url: "/monitor/sessions", params }),
      transformResponse: (response: { sessions: MonitorSession[]; page_context: PageContext }) => ({ items: response.sessions, pageContext: response.page_context }),
      providesTags: ["ProctorSessionList"],
    }),
    getMonitorSession: build.query<{ session: MonitorSessionDetail; events: Record<string, unknown>[]; directives: Directive[] }, string>({
      query: (sessionId) => `/monitor/sessions/${sessionId}`,
      providesTags: (_result, _error, sessionId) => [{ type: "ProctorSession", id: sessionId }],
    }),
    warnSession: build.mutation<void, { sessionId: string; message: string }>({
      query: ({ sessionId, message }) => ({ url: `/monitor/sessions/${sessionId}/warn`, method: "POST", body: { message } }),
      invalidatesTags: (_result, _error, { sessionId }) => [{ type: "ProctorSession", id: sessionId }],
    }),
    pauseSession: build.mutation<void, { sessionId: string; message?: string }>({
      query: ({ sessionId, message }) => ({ url: `/monitor/sessions/${sessionId}/pause`, method: "POST", body: { message } }),
      invalidatesTags: (_result, _error, { sessionId }) => [{ type: "ProctorSession", id: sessionId }, "ProctorSessionList"],
    }),
    resumeSession: build.mutation<void, string>({
      query: (sessionId) => ({ url: `/monitor/sessions/${sessionId}/resume`, method: "POST" }),
      invalidatesTags: (_result, _error, sessionId) => [{ type: "ProctorSession", id: sessionId }, "ProctorSessionList"],
    }),
    terminateSession: build.mutation<void, { sessionId: string; message?: string }>({
      query: ({ sessionId, message }) => ({ url: `/monitor/sessions/${sessionId}/terminate`, method: "POST", body: { message } }),
      invalidatesTags: (_result, _error, { sessionId }) => [{ type: "ProctorSession", id: sessionId }, "ProctorSessionList"],
    }),
  }),
});

export const {
  useListMonitorSessionsQuery,
  useGetMonitorSessionQuery,
  useWarnSessionMutation,
  usePauseSessionMutation,
  useResumeSessionMutation,
  useTerminateSessionMutation,
} = monitorApi;
