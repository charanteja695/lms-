import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { Submission, SubmissionFilters, SubmissionListItem } from "@/modules/code-execution/submissions/types";

export const submissionsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listSubmissions: build.query<ListResult<SubmissionListItem>, SubmissionFilters & PageParams>({
      query: (params) => ({ url: "/submissions", params }),
      transformResponse: (response: { submissions: SubmissionListItem[]; page_context: PageContext }) => ({
        items: response.submissions,
        pageContext: response.page_context,
      }),
      providesTags: ["SubmissionList"],
    }),
    /** `wait` long-polls until the submission is judged. */
    getSubmission: build.query<Submission, { submissionId: string; wait?: number }>({
      query: ({ submissionId, wait }) => ({ url: `/submissions/${submissionId}`, params: wait ? { wait } : undefined }),
      transformResponse: (response: { submission: Submission }) => response.submission,
      providesTags: (_result, _error, { submissionId }) => [{ type: "Submission", id: submissionId }],
    }),
  }),
});

export const { useListSubmissionsQuery, useGetSubmissionQuery, useLazyGetSubmissionQuery } = submissionsApi;
