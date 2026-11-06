import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { Job } from "@/modules/user-management/downloads/types";

export const jobsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listJobs: build.query<ListResult<Job>, PageParams>({
      query: (params) => ({ url: "/jobs", params }),
      transformResponse: (response: { jobs: Job[]; page_context: PageContext }) => ({
        items: response.jobs,
        pageContext: response.page_context,
      }),
      providesTags: ["Job"],
    }),
    getJob: build.query<Job, string>({
      query: (jobId) => `/jobs/${jobId}`,
      transformResponse: (response: { job: Job }) => response.job,
      providesTags: (_result, _error, id) => [{ type: "Job", id }],
    }),
  }),
});

export const { useListJobsQuery, useGetJobQuery } = jobsApi;
