import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { BoardFilters, CandidateJob, JobPreferences } from "@/modules/job-portal/board/types";

export type ResumeToApply = { resume_id: string; title: string; target_role: string | null; latest_version_no: number; ats_score?: number | null };

type JobPage = { jobs: CandidateJob[]; page_context: PageContext };
const toList = (response: JobPage): ListResult<CandidateJob> => ({ items: response.jobs, pageContext: response.page_context });

export const boardApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    searchJobs: build.query<ListResult<CandidateJob>, BoardFilters & PageParams>({
      query: (params) => ({ url: "/job-board", params }),
      transformResponse: toList,
      providesTags: ["JobBoard"],
    }),
    getBoardJob: build.query<CandidateJob, string>({
      query: (jobId) => `/job-board/${jobId}`,
      transformResponse: (response: { job: CandidateJob }) => response.job,
      providesTags: ["JobBoard"],
    }),
    listRecommendations: build.query<ListResult<CandidateJob>, PageParams>({
      query: (params) => ({ url: "/recommendations", params }),
      transformResponse: toList,
      providesTags: ["JobBoard"],
    }),
    getJobPreferences: build.query<JobPreferences, void>({
      query: () => "/job-preferences",
      transformResponse: (response: { preferences: JobPreferences }) => response.preferences,
      providesTags: ["JobPreferences"],
    }),
    saveJobPreferences: build.mutation<JobPreferences, Partial<JobPreferences>>({
      query: (body) => ({ url: "/job-preferences", method: "PUT", body }),
      transformResponse: (response: { preferences: JobPreferences }) => response.preferences,
      invalidatesTags: ["JobPreferences", "JobBoard"],
    }),
    applyToJob: build.mutation<{ application_id: string }, { jobId: string; resume_id: string; cover_note?: string }>({
      query: ({ jobId, ...body }) => ({ url: `/job-board/${jobId}/apply`, method: "POST", body }),
      transformResponse: (response: { application: { application_id: string } }) => response.application,
      invalidatesTags: ["JobBoard", "MyApplication"],
    }),
    /** The student's resumes (career-service) to apply with — this module's own read of `/resumes` (rule 5). */
    listResumesToApply: build.query<ResumeToApply[], void>({
      query: () => ({ url: "/resumes", params: { per_page: 50 } }),
      transformResponse: (response: { resumes: ResumeToApply[] }) => response.resumes,
      providesTags: ["ResumeList"],
    }),
  }),
});

export const {
  useSearchJobsQuery,
  useGetBoardJobQuery,
  useListRecommendationsQuery,
  useGetJobPreferencesQuery,
  useSaveJobPreferencesMutation,
  useApplyToJobMutation,
  useListResumesToApplyQuery,
} = boardApi;
