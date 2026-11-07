import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { GradeBody, GradingQueueItem } from "@/modules/assessments/attempts/gradingTypes";
import type { AttemptPaper, AttemptState, SavedAnswer } from "@/modules/assessments/attempts/paperTypes";
import type { AttemptResultView } from "@/modules/assessments/attempts/resultTypes";
import type { AttemptEvent, AttemptFilters, AttemptListItem, MyTest, MyTestFilters } from "@/modules/assessments/attempts/types";

export const attemptsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listMyTests: build.query<MyTest[], MyTestFilters>({
      query: (params) => ({ url: "/my/tests", params }),
      transformResponse: (response: { tests: MyTest[] }) => response.tests,
      providesTags: ["MyTestList"],
    }),
    getMyTest: build.query<MyTest, string>({
      query: (testId) => `/my/tests/${testId}`,
      transformResponse: (response: { test: MyTest }) => response.test,
      providesTags: (_result, _error, testId) => [{ type: "MyTest", id: testId }],
    }),
    prepareAttempt: build.mutation<AttemptPaper, { testId: string; startNow?: boolean }>({
      query: ({ testId, startNow }) => ({ url: `/tests/${testId}/attempts`, method: "POST", body: { start_now: startNow } }),
      transformResponse: (response: { attempt: AttemptState; questions: AttemptPaper["questions"] }) => ({ attempt: response.attempt, questions: response.questions }),
      invalidatesTags: ["MyTestList"],
    }),
    startAttempt: build.mutation<AttemptPaper, string>({
      query: (attemptId) => ({ url: `/attempts/${attemptId}/start`, method: "POST" }),
      transformResponse: (response: { attempt: AttemptState; questions: AttemptPaper["questions"] }) => ({ attempt: response.attempt, questions: response.questions }),
      invalidatesTags: ["MyTestList"],
    }),
    resumeAttempt: build.mutation<AttemptPaper, string>({
      query: (attemptId) => ({ url: `/attempts/${attemptId}/resume`, method: "POST" }),
      transformResponse: (response: { attempt: AttemptState; questions: AttemptPaper["questions"] }) => ({ attempt: response.attempt, questions: response.questions }),
    }),
    getAttemptState: build.query<AttemptState, string>({
      query: (attemptId) => `/attempts/${attemptId}`,
      transformResponse: (response: { attempt: AttemptState }) => response.attempt,
      providesTags: (_result, _error, attemptId) => [{ type: "Attempt", id: attemptId }],
    }),
    saveAnswer: build.mutation<SavedAnswer, { attemptId: string; questionId: string; response: Record<string, unknown> | null; revision: number; flagged?: boolean }>({
      query: ({ attemptId, questionId, response, revision, flagged }) => ({
        url: `/attempts/${attemptId}/answers/${questionId}`,
        method: "PUT",
        body: { response, revision, flagged },
      }),
      transformResponse: (response: SavedAnswer) => response,
    }),
    getFileUploadUrl: build.mutation<{ upload: { url: string; fields: Record<string, string> }; key: string }, { attemptId: string; questionId: string; fileName: string; contentType: string; sizeBytes: number }>({
      query: ({ attemptId, questionId, fileName, contentType, sizeBytes }) => ({
        url: `/attempts/${attemptId}/answers/${questionId}/file-upload-url`,
        method: "POST",
        body: { file_name: fileName, content_type: contentType, size_bytes: sizeBytes },
      }),
    }),
    finishSection: build.mutation<AttemptState, string>({
      query: (attemptId) => ({ url: `/attempts/${attemptId}/finish-section`, method: "POST" }),
      transformResponse: (response: { attempt: AttemptState }) => response.attempt,
      invalidatesTags: (_result, _error, attemptId) => [{ type: "Attempt", id: attemptId }],
    }),
    submitAttempt: build.mutation<void, string>({
      query: (attemptId) => ({ url: `/attempts/${attemptId}/submit`, method: "POST" }),
      invalidatesTags: (_result, _error, attemptId) => [{ type: "Attempt", id: attemptId }, { type: "AttemptResult", id: attemptId }, "MyTestList"],
    }),
    getResult: build.query<AttemptResultView, string>({
      query: (attemptId) => `/attempts/${attemptId}/result`,
      transformResponse: (response: { result: AttemptResultView }) => response.result,
      providesTags: (_result, _error, attemptId) => [{ type: "AttemptResult", id: attemptId }],
    }),

    listAttempts: build.query<ListResult<AttemptListItem>, AttemptFilters & PageParams>({
      query: (params) => ({ url: "/attempts", params }),
      transformResponse: (response: { attempts: AttemptListItem[]; page_context: PageContext }) => ({ items: response.attempts, pageContext: response.page_context }),
      providesTags: ["AttemptList"],
    }),
    getAttemptEvents: build.query<AttemptEvent[], string>({
      query: (attemptId) => `/attempts/${attemptId}/events`,
      transformResponse: (response: { events: AttemptEvent[] }) => response.events,
      providesTags: (_result, _error, attemptId) => [{ type: "AttemptEvents", id: attemptId }],
    }),
    pauseAttempt: build.mutation<AttemptListItem, { attemptId: string; reason?: string | null }>({
      query: ({ attemptId, reason }) => ({ url: `/attempts/${attemptId}/pause`, method: "POST", body: { reason } }),
      transformResponse: (response: { attempt: AttemptListItem }) => response.attempt,
      invalidatesTags: (_result, _error, { attemptId }) => [{ type: "Attempt", id: attemptId }, "AttemptList"],
    }),
    unpauseAttempt: build.mutation<AttemptListItem, string>({
      query: (attemptId) => ({ url: `/attempts/${attemptId}/unpause`, method: "POST" }),
      transformResponse: (response: { attempt: AttemptListItem }) => response.attempt,
      invalidatesTags: (_result, _error, attemptId) => [{ type: "Attempt", id: attemptId }, "AttemptList"],
    }),
    terminateAttempt: build.mutation<AttemptListItem, { attemptId: string; reason?: string | null }>({
      query: ({ attemptId, reason }) => ({ url: `/attempts/${attemptId}/terminate`, method: "POST", body: { reason } }),
      transformResponse: (response: { attempt: AttemptListItem }) => response.attempt,
      invalidatesTags: (_result, _error, { attemptId }) => [{ type: "Attempt", id: attemptId }, "AttemptList"],
    }),
    regradeAttempt: build.mutation<AttemptListItem, string>({
      query: (attemptId) => ({ url: `/attempts/${attemptId}/regrade`, method: "POST" }),
      transformResponse: (response: { attempt: AttemptListItem }) => response.attempt,
      invalidatesTags: (_result, _error, attemptId) => [{ type: "Attempt", id: attemptId }, "AttemptList"],
    }),

    getGradingQueue: build.query<ListResult<GradingQueueItem>, { test_id?: string } & PageParams>({
      query: (params) => ({ url: "/grading/queue", params }),
      transformResponse: (response: { items: GradingQueueItem[]; page_context: PageContext }) => ({ items: response.items, pageContext: response.page_context }),
      providesTags: ["GradingQueue"],
    }),
    gradeAnswer: build.mutation<void, { attemptId: string; questionId: string; body: GradeBody }>({
      query: ({ attemptId, questionId, body }) => ({ url: `/attempts/${attemptId}/answers/${questionId}/grade`, method: "PUT", body }),
      invalidatesTags: (_result, _error, { attemptId }) => ["GradingQueue", { type: "Attempt", id: attemptId }, "AttemptList"],
    }),
    /** A short-lived link to a file a student uploaded as an answer (graders, exam managers and the student). */
    getAnswerFileLink: build.mutation<{ filename: string; url: string }, { attemptId: string; questionId: string; index: number }>({
      query: ({ attemptId, questionId, index }) => ({ url: `/attempts/${attemptId}/answers/${questionId}/files/${index}`, method: "GET" }),
      transformResponse: (response: { file: { filename: string; url: string } }) => response.file,
    }),
  }),
});

export const {
  useListMyTestsQuery,
  useGetMyTestQuery,
  usePrepareAttemptMutation,
  useStartAttemptMutation,
  useResumeAttemptMutation,
  useGetAttemptStateQuery,
  useSaveAnswerMutation,
  useGetFileUploadUrlMutation,
  useFinishSectionMutation,
  useSubmitAttemptMutation,
  useGetResultQuery,
  useLazyGetResultQuery,
  useListAttemptsQuery,
  useGetAttemptEventsQuery,
  usePauseAttemptMutation,
  useUnpauseAttemptMutation,
  useTerminateAttemptMutation,
  useRegradeAttemptMutation,
  useGetGradingQueueQuery,
  useGradeAnswerMutation,
  useGetAnswerFileLinkMutation,
} = attemptsApi;
