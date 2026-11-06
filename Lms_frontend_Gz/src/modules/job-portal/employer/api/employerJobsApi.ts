import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { Company, EmployerJob, JobAction, JobBody, JobStatus } from "@/modules/job-portal/employer/types";

const jobTags = (jobId: string) => [{ type: "EmployerJob" as const, id: jobId }, "EmployerJobList" as const];
type JobResponse = { job: EmployerJob };

export const employerJobsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getMyCompany: build.query<Company, void>({
      query: () => "/employer/profile",
      transformResponse: (response: { employer: Company }) => response.employer,
      providesTags: ["EmployerProfile"],
    }),
    updateMyCompany: build.mutation<Company, Partial<Pick<Company, "about" | "website" | "industry" | "company_size" | "headquarters">>>({
      query: (body) => ({ url: "/employer/profile", method: "PATCH", body }),
      transformResponse: (response: { employer: Company }) => response.employer,
      invalidatesTags: ["EmployerProfile"],
    }),
    submitMyCompany: build.mutation<Company, void>({
      query: () => ({ url: "/employer/profile/submit", method: "POST" }),
      transformResponse: (response: { employer: Company }) => response.employer,
      invalidatesTags: ["EmployerProfile"],
    }),
    listEmployerJobs: build.query<ListResult<EmployerJob>, { status?: JobStatus; q?: string; employer_org_id?: string } & PageParams>({
      query: (params) => ({ url: "/employer/jobs", params }),
      transformResponse: (response: { jobs: EmployerJob[]; page_context: PageContext }) => ({ items: response.jobs, pageContext: response.page_context }),
      providesTags: ["EmployerJobList"],
    }),
    getEmployerJob: build.query<EmployerJob, string>({
      query: (jobId) => `/employer/jobs/${jobId}`,
      transformResponse: (response: JobResponse) => response.job,
      providesTags: (_r, _e, jobId) => [{ type: "EmployerJob", id: jobId }],
    }),
    createEmployerJob: build.mutation<EmployerJob, JobBody>({
      query: (body) => ({ url: "/employer/jobs", method: "POST", body }),
      transformResponse: (response: JobResponse) => response.job,
      invalidatesTags: ["EmployerJobList"],
    }),
    updateEmployerJob: build.mutation<EmployerJob, { jobId: string; body: Partial<JobBody> }>({
      query: ({ jobId, body }) => ({ url: `/employer/jobs/${jobId}`, method: "PATCH", body }),
      transformResponse: (response: JobResponse) => response.job,
      invalidatesTags: (_r, _e, { jobId }) => jobTags(jobId),
    }),
    jobAction: build.mutation<EmployerJob, { jobId: string; action: JobAction }>({
      query: ({ jobId, action }) => ({ url: `/employer/jobs/${jobId}/${action}`, method: "POST" }),
      transformResponse: (response: JobResponse) => response.job,
      invalidatesTags: (_r, _e, { jobId }) => jobTags(jobId),
    }),
    closeJob: build.mutation<EmployerJob, { jobId: string; reason: string }>({
      query: ({ jobId, reason }) => ({ url: `/employer/jobs/${jobId}/close`, method: "POST", body: { reason } }),
      transformResponse: (response: JobResponse) => response.job,
      invalidatesTags: (_r, _e, { jobId }) => jobTags(jobId),
    }),
    deleteEmployerJob: build.mutation<{ message: string }, string>({
      query: (jobId) => ({ url: `/employer/jobs/${jobId}`, method: "DELETE" }),
      invalidatesTags: ["EmployerJobList"],
    }),
  }),
});

export const {
  useGetMyCompanyQuery,
  useUpdateMyCompanyMutation,
  useSubmitMyCompanyMutation,
  useListEmployerJobsQuery,
  useGetEmployerJobQuery,
  useCreateEmployerJobMutation,
  useUpdateEmployerJobMutation,
  useJobActionMutation,
  useCloseJobMutation,
  useDeleteEmployerJobMutation,
} = employerJobsApi;
