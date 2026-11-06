import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { EmployerStatus, JobStatus } from "@/modules/job-portal/common/types";
import type { Company, EmployerJob } from "@/modules/job-portal/employer/types";

/** Careers managers: verify companies and approve jobs before they go live. */
export const jobAdminApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listEmployersForReview: build.query<ListResult<Company>, { status?: EmployerStatus } & PageParams>({
      query: (params) => ({ url: "/admin/employers", params }),
      transformResponse: (response: { employers: Company[]; page_context: PageContext }) => ({ items: response.employers, pageContext: response.page_context }),
      providesTags: ["JobAdmin"],
    }),
    reviewEmployer: build.mutation<Company, { id: string; approve: boolean; note?: string }>({
      query: ({ id, ...body }) => ({ url: `/admin/employers/${id}/review`, method: "POST", body }),
      invalidatesTags: ["JobAdmin"],
    }),
    suspendEmployer: build.mutation<Company, { id: string; note: string }>({
      query: ({ id, note }) => ({ url: `/admin/employers/${id}/suspend`, method: "POST", body: { note } }),
      invalidatesTags: ["JobAdmin"],
    }),
    reinstateEmployer: build.mutation<Company, string>({
      query: (id) => ({ url: `/admin/employers/${id}/reinstate`, method: "POST" }),
      invalidatesTags: ["JobAdmin"],
    }),
    listJobsForReview: build.query<ListResult<EmployerJob>, { status?: JobStatus } & PageParams>({
      query: (params) => ({ url: "/admin/jobs", params }),
      transformResponse: (response: { jobs: EmployerJob[]; page_context: PageContext }) => ({ items: response.jobs, pageContext: response.page_context }),
      providesTags: ["JobAdmin"],
    }),
    reviewJob: build.mutation<EmployerJob, { id: string; approve: boolean; note?: string }>({
      query: ({ id, ...body }) => ({ url: `/admin/jobs/${id}/review`, method: "POST", body }),
      invalidatesTags: ["JobAdmin", "EmployerJob", "EmployerJobList"],
    }),
  }),
});

export const { useListEmployersForReviewQuery, useReviewEmployerMutation, useSuspendEmployerMutation, useReinstateEmployerMutation, useListJobsForReviewQuery, useReviewJobMutation } = jobAdminApi;
