import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type {
  Problem,
  ProblemAuthor,
  ProblemCreateBody,
  ProblemFilters,
  ProblemListItem,
  ProblemStats,
  ProblemUpdateBody,
  SavedCode,
  TestCase,
  TestCaseCreateBody,
  TestCaseUpdateBody,
} from "@/modules/code-execution/problems/types";
import type { Submission, SubmissionCreateBody } from "@/modules/code-execution/submissions/types";

export const problemsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listProblems: build.query<ListResult<ProblemListItem>, ProblemFilters & PageParams>({
      query: (params) => ({ url: "/problems", params }),
      transformResponse: (response: { problems: ProblemListItem[]; page_context: PageContext }) => ({
        items: response.problems,
        pageContext: response.page_context,
      }),
      providesTags: ["ProblemList"],
    }),
    getProblem: build.query<Problem, string>({
      query: (id) => `/problems/${id}`,
      transformResponse: (response: { problem: Problem }) => response.problem,
      providesTags: (_result, _error, id) => [{ type: "Problem", id }],
    }),
    createProblem: build.mutation<ProblemAuthor, ProblemCreateBody>({
      query: (body) => ({ url: "/problems", method: "POST", body }),
      transformResponse: (response: { problem: ProblemAuthor }) => response.problem,
      invalidatesTags: ["ProblemList"],
    }),
    updateProblem: build.mutation<ProblemAuthor, { problemId: string; body: ProblemUpdateBody }>({
      query: ({ problemId, body }) => ({ url: `/problems/${problemId}`, method: "PATCH", body }),
      transformResponse: (response: { problem: ProblemAuthor }) => response.problem,
      invalidatesTags: (_result, _error, { problemId }) => [{ type: "Problem", id: problemId }, { type: "ProblemAuthor", id: problemId }, "ProblemList"],
    }),
    deleteProblem: build.mutation<void, string>({
      query: (id) => ({ url: `/problems/${id}`, method: "DELETE" }),
      invalidatesTags: ["ProblemList"],
    }),
    getProblemAuthor: build.query<ProblemAuthor, string>({
      query: (id) => `/problems/${id}/author`,
      transformResponse: (response: { problem: ProblemAuthor }) => response.problem,
      providesTags: (_result, _error, id) => [{ type: "ProblemAuthor", id }],
    }),
    publishProblem: build.mutation<ProblemAuthor, string>({
      query: (id) => ({ url: `/problems/${id}/publish`, method: "POST" }),
      transformResponse: (response: { problem: ProblemAuthor }) => response.problem,
      invalidatesTags: (_result, _error, id) => [{ type: "Problem", id }, { type: "ProblemAuthor", id }, "ProblemList"],
    }),
    retireProblem: build.mutation<ProblemAuthor, string>({
      query: (id) => ({ url: `/problems/${id}/retire`, method: "POST" }),
      transformResponse: (response: { problem: ProblemAuthor }) => response.problem,
      invalidatesTags: (_result, _error, id) => [{ type: "Problem", id }, { type: "ProblemAuthor", id }, "ProblemList"],
    }),
    getProblemStats: build.query<ProblemStats, string>({
      query: (id) => `/problems/${id}/stats`,
      transformResponse: (response: { stats: ProblemStats }) => response.stats,
      providesTags: (_result, _error, id) => [{ type: "ProblemStats", id }],
    }),

    listTestCases: build.query<TestCase[], string>({
      query: (problemId) => `/problems/${problemId}/test-cases`,
      transformResponse: (response: { test_cases: TestCase[] }) => response.test_cases,
      providesTags: (_result, _error, problemId) => [{ type: "TestCaseList", id: problemId }],
    }),
    createTestCase: build.mutation<TestCase, { problemId: string; body: TestCaseCreateBody }>({
      query: ({ problemId, body }) => ({ url: `/problems/${problemId}/test-cases`, method: "POST", body }),
      transformResponse: (response: { test_case: TestCase }) => response.test_case,
      invalidatesTags: (_result, _error, { problemId }) => [{ type: "TestCaseList", id: problemId }, { type: "ProblemAuthor", id: problemId }],
    }),
    bulkCreateTestCases: build.mutation<void, { problemId: string; testCases: TestCaseCreateBody[] }>({
      query: ({ problemId, testCases }) => ({ url: `/problems/${problemId}/test-cases/bulk`, method: "POST", body: { test_cases: testCases } }),
      invalidatesTags: (_result, _error, { problemId }) => [{ type: "TestCaseList", id: problemId }, { type: "ProblemAuthor", id: problemId }],
    }),
    reorderTestCases: build.mutation<void, { problemId: string; testCaseIds: string[] }>({
      query: ({ problemId, testCaseIds }) => ({ url: `/problems/${problemId}/test-cases/reorder`, method: "POST", body: { test_case_ids: testCaseIds } }),
      invalidatesTags: (_result, _error, { problemId }) => [{ type: "TestCaseList", id: problemId }],
    }),
    updateTestCase: build.mutation<TestCase, { problemId: string; testCaseId: string; body: TestCaseUpdateBody }>({
      query: ({ problemId, testCaseId, body }) => ({ url: `/problems/${problemId}/test-cases/${testCaseId}`, method: "PATCH", body }),
      transformResponse: (response: { test_case: TestCase }) => response.test_case,
      invalidatesTags: (_result, _error, { problemId }) => [{ type: "TestCaseList", id: problemId }],
    }),
    deleteTestCase: build.mutation<void, { problemId: string; testCaseId: string }>({
      query: ({ problemId, testCaseId }) => ({ url: `/problems/${problemId}/test-cases/${testCaseId}`, method: "DELETE" }),
      invalidatesTags: (_result, _error, { problemId }) => [{ type: "TestCaseList", id: problemId }, { type: "ProblemAuthor", id: problemId }],
    }),

    getSavedCode: build.query<SavedCode, { problemId: string; language: string }>({
      query: ({ problemId, language }) => `/problems/${problemId}/code/${language}`,
      transformResponse: (response: { saved_code: SavedCode }) => response.saved_code,
      providesTags: (_result, _error, { problemId, language }) => [{ type: "SavedCode", id: `${problemId}:${language}` }],
    }),
    saveCode: build.mutation<SavedCode, { problemId: string; language: string; source: string }>({
      query: ({ problemId, language, source }) => ({ url: `/problems/${problemId}/code/${language}`, method: "PUT", body: { source } }),
      transformResponse: (response: { saved_code: SavedCode }) => response.saved_code,
      invalidatesTags: (_result, _error, { problemId, language }) => [{ type: "SavedCode", id: `${problemId}:${language}` }],
    }),

    createSubmission: build.mutation<Submission, { problemId: string; body: SubmissionCreateBody }>({
      query: ({ problemId, body }) => ({ url: `/problems/${problemId}/submissions`, method: "POST", body }),
      transformResponse: (response: { submission: Submission }) => response.submission,
      invalidatesTags: (_result, _error, { problemId }) => ["SubmissionList", { type: "Problem", id: problemId }, { type: "ProblemList" }],
    }),
  }),
});

export const {
  useListProblemsQuery,
  useGetProblemQuery,
  useCreateProblemMutation,
  useUpdateProblemMutation,
  useDeleteProblemMutation,
  useGetProblemAuthorQuery,
  usePublishProblemMutation,
  useRetireProblemMutation,
  useGetProblemStatsQuery,
  useListTestCasesQuery,
  useCreateTestCaseMutation,
  useBulkCreateTestCasesMutation,
  useReorderTestCasesMutation,
  useUpdateTestCaseMutation,
  useDeleteTestCaseMutation,
  useGetSavedCodeQuery,
  useSaveCodeMutation,
  useCreateSubmissionMutation,
} = problemsApi;
