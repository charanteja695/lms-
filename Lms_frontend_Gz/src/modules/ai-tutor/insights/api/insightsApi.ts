import { baseApi } from "@/core/api/baseApi";
import type { DownvotedAnswer, EvalCase, EvalRun, EvalSet, EvalSetDetail, FeedbackSummary, IndexVersion } from "@/modules/ai-tutor/insights/types";

export const insightsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getFeedbackSummary: build.query<FeedbackSummary, string>({
      query: (courseId) => ({ url: "/feedback/summary", params: { course_id: courseId } }),
      transformResponse: (response: { summary: FeedbackSummary }) => response.summary,
      providesTags: ["TutorFeedback"],
    }),
    getDownvoted: build.query<DownvotedAnswer[], string>({
      query: (courseId) => ({ url: "/feedback/downvoted", params: { course_id: courseId, limit: 50 } }),
      transformResponse: (response: { items: DownvotedAnswer[] }) => response.items,
      providesTags: ["TutorFeedback"],
    }),
    listEvalSets: build.query<EvalSet[], string>({
      query: (courseId) => ({ url: "/eval-sets", params: { course_id: courseId } }),
      transformResponse: (response: { eval_sets: EvalSet[] }) => response.eval_sets,
      providesTags: ["TutorEvalSetList"],
    }),
    createEvalSet: build.mutation<EvalSet, { course_id: string; name: string }>({
      query: (body) => ({ url: "/eval-sets", method: "POST", body }),
      transformResponse: (response: { eval_set: EvalSet }) => response.eval_set,
      invalidatesTags: ["TutorEvalSetList"],
    }),
    getEvalSet: build.query<EvalSetDetail, string>({
      query: (evalSetId) => `/eval-sets/${evalSetId}`,
      providesTags: (_result, _error, evalSetId) => [{ type: "TutorEvalSet", id: evalSetId }],
    }),
    addEvalCase: build.mutation<EvalCase, { evalSetId: string; question: string; expected_item_ids: string[] }>({
      query: ({ evalSetId, ...body }) => ({ url: `/eval-sets/${evalSetId}/cases`, method: "POST", body }),
      transformResponse: (response: { case: EvalCase }) => response.case,
      invalidatesTags: (_result, _error, { evalSetId }) => [{ type: "TutorEvalSet", id: evalSetId }],
    }),
    runEvalSet: build.mutation<EvalRun, { evalSetId: string; top_k?: number; version_id?: string }>({
      query: ({ evalSetId, ...body }) => ({ url: `/eval-sets/${evalSetId}/runs`, method: "POST", body }),
      transformResponse: (response: { run: EvalRun }) => response.run,
      invalidatesTags: (_result, _error, { evalSetId }) => [{ type: "TutorEvalSet", id: evalSetId }],
    }),
    getIndexStatus: build.query<IndexVersion[], string>({
      query: (courseId) => ({ url: "/index/status", params: { course_id: courseId } }),
      transformResponse: (response: { versions: IndexVersion[] }) => response.versions,
      providesTags: ["TutorIndex"],
    }),
    reindexVersion: build.mutation<void, string>({
      query: (versionId) => ({ url: "/index/reindex", method: "POST", body: { version_id: versionId } }),
      invalidatesTags: ["TutorIndex"],
    }),
  }),
});

export const {
  useGetFeedbackSummaryQuery,
  useGetDownvotedQuery,
  useListEvalSetsQuery,
  useCreateEvalSetMutation,
  useGetEvalSetQuery,
  useAddEvalCaseMutation,
  useRunEvalSetMutation,
  useGetIndexStatusQuery,
  useReindexVersionMutation,
} = insightsApi;
