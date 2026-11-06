import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type {
  Question,
  QuestionCreateBody,
  QuestionFilters,
  QuestionListItem,
  QuestionUpdateBody,
  QuestionVersion,
} from "@/modules/assessments/questions/types";

/** Each row is created or refused on its own; ``index`` is its position in the file. */
export interface BulkImportResult {
  created: number;
  failed: number;
  results: { index: number; question_id: string | null; error: string | null; details: { field?: string; message?: string }[] }[];
}

export const questionsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listQuestions: build.query<ListResult<QuestionListItem>, QuestionFilters & PageParams>({
      query: (params) => ({ url: "/questions", params }),
      transformResponse: (response: { questions: QuestionListItem[]; page_context: PageContext }) => ({
        items: response.questions,
        pageContext: response.page_context,
      }),
      providesTags: ["QuestionList"],
    }),
    getQuestion: build.query<Question, string>({
      query: (id) => `/questions/${id}`,
      transformResponse: (response: { question: Question }) => response.question,
      providesTags: (_result, _error, id) => [{ type: "Question", id }],
    }),
    importQuestions: build.mutation<BulkImportResult, { questions: unknown[]; key: string }>({
      query: ({ questions, key }) => ({ url: "/questions/bulk", method: "POST", body: { questions }, headers: { "Idempotency-Key": key } }),
      invalidatesTags: ["QuestionList"],
    }),
    createQuestion: build.mutation<Question, QuestionCreateBody>({
      query: (body) => ({ url: "/questions", method: "POST", body }),
      transformResponse: (response: { question: Question }) => response.question,
      invalidatesTags: ["QuestionList"],
    }),
    updateQuestion: build.mutation<Question, { questionId: string; body: QuestionUpdateBody }>({
      query: ({ questionId, body }) => ({ url: `/questions/${questionId}`, method: "PATCH", body }),
      transformResponse: (response: { question: Question }) => response.question,
      invalidatesTags: (_result, _error, { questionId }) => [{ type: "Question", id: questionId }, "QuestionList"],
    }),
    listQuestionVersions: build.query<QuestionVersion[], string>({
      query: (questionId) => `/questions/${questionId}/versions`,
      transformResponse: (response: { versions: QuestionVersion[] }) => response.versions,
      providesTags: (_result, _error, questionId) => [{ type: "QuestionVersionList", id: questionId }],
    }),
    submitQuestion: build.mutation<Question, string>({
      query: (id) => ({ url: `/questions/${id}/submit`, method: "POST" }),
      transformResponse: (response: { question: Question }) => response.question,
      invalidatesTags: (_result, _error, id) => [{ type: "Question", id }, "QuestionList"],
    }),
    approveQuestion: build.mutation<Question, { questionId: string; note?: string | null }>({
      query: ({ questionId, note }) => ({ url: `/questions/${questionId}/approve`, method: "POST", body: { note } }),
      transformResponse: (response: { question: Question }) => response.question,
      invalidatesTags: (_result, _error, { questionId }) => [{ type: "Question", id: questionId }, "QuestionList"],
    }),
    rejectQuestion: build.mutation<Question, { questionId: string; note: string }>({
      query: ({ questionId, note }) => ({ url: `/questions/${questionId}/reject`, method: "POST", body: { note } }),
      transformResponse: (response: { question: Question }) => response.question,
      invalidatesTags: (_result, _error, { questionId }) => [{ type: "Question", id: questionId }, "QuestionList"],
    }),
    deleteDraft: build.mutation<Question, string>({
      query: (id) => ({ url: `/questions/${id}/draft`, method: "DELETE" }),
      transformResponse: (response: { question: Question }) => response.question,
      invalidatesTags: (_result, _error, id) => [{ type: "Question", id }, "QuestionList"],
    }),
    retireQuestion: build.mutation<Question, string>({
      query: (id) => ({ url: `/questions/${id}/retire`, method: "POST" }),
      transformResponse: (response: { question: Question }) => response.question,
      invalidatesTags: (_result, _error, id) => [{ type: "Question", id }, "QuestionList"],
    }),
    restoreQuestion: build.mutation<Question, string>({
      query: (id) => ({ url: `/questions/${id}/restore`, method: "POST" }),
      transformResponse: (response: { question: Question }) => response.question,
      invalidatesTags: (_result, _error, id) => [{ type: "Question", id }, "QuestionList"],
    }),
    recomputeStats: build.mutation<Question, string>({
      query: (id) => ({ url: `/questions/${id}/stats/recompute`, method: "POST" }),
      transformResponse: (response: { question: Question }) => response.question,
      invalidatesTags: (_result, _error, id) => [{ type: "Question", id }],
    }),
  }),
});

export const {
  useListQuestionsQuery,
  useGetQuestionQuery,
  useCreateQuestionMutation,
  useUpdateQuestionMutation,
  useListQuestionVersionsQuery,
  useSubmitQuestionMutation,
  useApproveQuestionMutation,
  useRejectQuestionMutation,
  useDeleteDraftMutation,
  useRetireQuestionMutation,
  useRestoreQuestionMutation,
  useRecomputeStatsMutation,
  useImportQuestionsMutation,
} = questionsApi;
