import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { ReviewFilters, ReviewSubmission, ReviewSubmissionListItem, SimilarMatch } from "@/modules/code-execution/review/types";

export const reviewApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listReviewSubmissions: build.query<ListResult<ReviewSubmissionListItem>, ReviewFilters & PageParams>({
      query: (params) => ({ url: "/review/submissions", params }),
      transformResponse: (response: { submissions: ReviewSubmissionListItem[]; page_context: PageContext }) => ({
        items: response.submissions,
        pageContext: response.page_context,
      }),
      providesTags: ["ReviewSubmissionList"],
    }),
    getReviewSubmission: build.query<ReviewSubmission, string>({
      query: (id) => `/review/submissions/${id}`,
      transformResponse: (response: { submission: ReviewSubmission }) => response.submission,
      providesTags: (_result, _error, id) => [{ type: "ReviewSubmission", id }],
    }),
    getSimilarMatches: build.query<SimilarMatch[], string>({
      query: (id) => `/review/submissions/${id}/similar`,
      transformResponse: (response: { matches: SimilarMatch[] }) => response.matches,
    }),
  }),
});

export const { useListReviewSubmissionsQuery, useGetReviewSubmissionQuery, useGetSimilarMatchesQuery } = reviewApi;
