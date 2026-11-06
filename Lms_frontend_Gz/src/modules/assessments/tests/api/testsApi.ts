import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { PlagiarismItem, TestAnalytics, TestCompositionItem, TestValidation } from "@/modules/assessments/tests/reportTypes";
import type { Schedule, ScheduleCreateBody, ScheduleUpdateBody } from "@/modules/assessments/tests/scheduleTypes";
import type { SectionInput } from "@/modules/assessments/tests/sectionTypes";
import type { Test, TestCreateBody, TestFilters, TestListItem, TestUpdateBody } from "@/modules/assessments/tests/types";

export const testsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listTests: build.query<ListResult<TestListItem>, TestFilters & PageParams>({
      query: (params) => ({ url: "/tests", params }),
      transformResponse: (response: { tests: TestListItem[]; page_context: PageContext }) => ({ items: response.tests, pageContext: response.page_context }),
      providesTags: ["TestList"],
    }),
    /** For a course builder: each test's multiple-choice and program counts in one call. */
    getCompositions: build.query<TestCompositionItem[], string[]>({
      query: (testIds) => ({ url: "/tests/compositions", method: "POST", body: { test_ids: testIds } }),
      transformResponse: (response: { compositions: TestCompositionItem[] }) => response.compositions,
      providesTags: (result) => [...(result ?? []).map((item) => ({ type: "Test" as const, id: item.test_id })), "TestList"],
    }),
    getTest: build.query<Test, string>({
      query: (id) => `/tests/${id}`,
      transformResponse: (response: { test: Test }) => response.test,
      providesTags: (_result, _error, id) => [{ type: "Test", id }],
    }),
    createTest: build.mutation<Test, TestCreateBody>({
      query: (body) => ({ url: "/tests", method: "POST", body }),
      transformResponse: (response: { test: Test }) => response.test,
      invalidatesTags: ["TestList"],
    }),
    updateTest: build.mutation<Test, { testId: string; body: TestUpdateBody }>({
      query: ({ testId, body }) => ({ url: `/tests/${testId}`, method: "PATCH", body }),
      transformResponse: (response: { test: Test }) => response.test,
      invalidatesTags: (_result, _error, { testId }) => [{ type: "Test", id: testId }, "TestList"],
    }),
    deleteTest: build.mutation<void, string>({
      query: (id) => ({ url: `/tests/${id}`, method: "DELETE" }),
      invalidatesTags: ["TestList"],
    }),
    replaceSections: build.mutation<Test, { testId: string; sections: SectionInput[] }>({
      query: ({ testId, sections }) => ({ url: `/tests/${testId}/sections`, method: "PUT", body: { sections } }),
      transformResponse: (response: { test: Test }) => response.test,
      invalidatesTags: (_result, _error, { testId }) => [{ type: "Test", id: testId }],
    }),
    getValidation: build.query<TestValidation, string>({
      query: (id) => `/tests/${id}/validation`,
      transformResponse: (response: TestValidation) => response,
      providesTags: (_result, _error, id) => [{ type: "Test", id }],
    }),
    submitTest: build.mutation<Test, string>({
      query: (id) => ({ url: `/tests/${id}/submit`, method: "POST" }),
      transformResponse: (response: { test: Test }) => response.test,
      invalidatesTags: (_result, _error, id) => [{ type: "Test", id }, "TestList"],
    }),
    approveTest: build.mutation<Test, { testId: string; note?: string | null }>({
      query: ({ testId, note }) => ({ url: `/tests/${testId}/approve`, method: "POST", body: { note } }),
      transformResponse: (response: { test: Test }) => response.test,
      invalidatesTags: (_result, _error, { testId }) => [{ type: "Test", id: testId }, "TestList"],
    }),
    rejectTest: build.mutation<Test, { testId: string; note: string }>({
      query: ({ testId, note }) => ({ url: `/tests/${testId}/reject`, method: "POST", body: { note } }),
      transformResponse: (response: { test: Test }) => response.test,
      invalidatesTags: (_result, _error, { testId }) => [{ type: "Test", id: testId }, "TestList"],
    }),
    retireTest: build.mutation<Test, string>({
      query: (id) => ({ url: `/tests/${id}/retire`, method: "POST" }),
      transformResponse: (response: { test: Test }) => response.test,
      invalidatesTags: (_result, _error, id) => [{ type: "Test", id }, "TestList"],
    }),
    // Add question to test (used after import)
    addQuestionToTest: build.mutation<void, { testId: string; questionId: string }>({
      query: ({ testId, questionId }) => ({
        url: `/tests/${testId}/questions`,
        method: "POST",
        body: { question_id: questionId },
      }),
      invalidatesTags: (_result, _error, { testId }) => [{ type: "Test", id: testId }],
    }),
    cloneTest: build.mutation<Test, string>({
      query: (id) => ({ url: `/tests/${id}/clone`, method: "POST" }),
      transformResponse: (response: { test: Test }) => response.test,
      invalidatesTags: ["TestList"],
    }),
    listSchedules: build.query<Schedule[], string>({
      query: (testId) => `/tests/${testId}/schedules`,
      transformResponse: (response: { schedules: Schedule[] }) => response.schedules,
      providesTags: (_result, _error, testId) => [{ type: "TestSchedules", id: testId }],
    }),
    createSchedule: build.mutation<Schedule, { testId: string; body: ScheduleCreateBody }>({
      query: ({ testId, body }) => ({ url: `/tests/${testId}/schedules`, method: "POST", body }),
      transformResponse: (response: { schedule: Schedule }) => response.schedule,
      invalidatesTags: (_result, _error, { testId }) => [{ type: "TestSchedules", id: testId }],
    }),
    updateSchedule: build.mutation<Schedule, { testId: string; scheduleId: string; body: ScheduleUpdateBody }>({
      query: ({ testId, scheduleId, body }) => ({ url: `/tests/${testId}/schedules/${scheduleId}`, method: "PATCH", body }),
      transformResponse: (response: { schedule: Schedule }) => response.schedule,
      invalidatesTags: (_result, _error, { testId }) => [{ type: "TestSchedules", id: testId }],
    }),
    cancelSchedule: build.mutation<void, { testId: string; scheduleId: string }>({
      query: ({ testId, scheduleId }) => ({ url: `/tests/${testId}/schedules/${scheduleId}`, method: "DELETE" }),
      invalidatesTags: (_result, _error, { testId }) => [{ type: "TestSchedules", id: testId }],
    }),
    getAnalytics: build.query<TestAnalytics, string>({
      query: (testId) => `/tests/${testId}/analytics`,
      transformResponse: (response: { analytics: TestAnalytics }) => response.analytics,
      providesTags: (_result, _error, testId) => [{ type: "TestAnalytics", id: testId }],
    }),
    getPlagiarism: build.query<PlagiarismItem[], string>({
      query: (testId) => `/tests/${testId}/plagiarism`,
      transformResponse: (response: { items: PlagiarismItem[] }) => response.items,
      providesTags: (_result, _error, testId) => [{ type: "TestPlagiarism", id: testId }],
    }),
    releaseResults: build.mutation<void, string>({
      query: (testId) => ({ url: `/tests/${testId}/release-results`, method: "POST" }),
      invalidatesTags: (_result, _error, testId) => [{ type: "TestResults", id: testId }, { type: "Test", id: testId }],
    }),
  }),
});

export const {
  useListTestsQuery,
  useGetTestQuery,
  useLazyGetTestQuery,
  useGetCompositionsQuery,
  useCreateTestMutation,
  useUpdateTestMutation,
  useDeleteTestMutation,
  useReplaceSectionsMutation,
  useGetValidationQuery,
  useLazyGetValidationQuery,
  useSubmitTestMutation,
  useApproveTestMutation,
  useRejectTestMutation,
  useRetireTestMutation,
  useCloneTestMutation,
  useAddQuestionToTestMutation,
  useListSchedulesQuery,
  useCreateScheduleMutation,
  useUpdateScheduleMutation,
  useCancelScheduleMutation,
  useGetAnalyticsQuery,
  useGetPlagiarismQuery,
  useReleaseResultsMutation,
} = testsApi;
