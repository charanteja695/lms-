import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { ApplicationStatus } from "@/modules/job-portal/common/types";
import type { Applicant, ApplicantDetail, Funnel, Ranking, ScreeningDecision } from "@/modules/job-portal/employer/pipelineTypes";

const jobApplicantTags = ["JobApplicants" as const, "EmployerJob" as const];

export interface ApplicantFilters {
  status?: ApplicationStatus | ApplicationStatus[];
  min_score?: number;
  q?: string;
  sort?: "screen" | "match" | "recent";
}

/** The recruiter's pipeline. Only a person rejects (a confirmed batch); the AI ranking never changes an application. */
export const pipelineApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listApplicants: build.query<ListResult<Applicant>, { jobId: string } & ApplicantFilters & PageParams>({
      query: ({ jobId, ...params }) => ({ url: `/employer/jobs/${jobId}/applications`, params }),
      transformResponse: (response: { applications: Applicant[]; page_context: PageContext }) => ({ items: response.applications, pageContext: response.page_context }),
      providesTags: ["JobApplicants"],
    }),
    getFunnel: build.query<Funnel, string>({
      query: (jobId) => `/employer/jobs/${jobId}/funnel`,
      providesTags: ["JobApplicants"],
    }),
    getRanking: build.query<Ranking, { jobId: string; shortlist_at?: number; reject_below?: number }>({
      query: ({ jobId, ...params }) => ({ url: `/employer/jobs/${jobId}/screening`, params }),
      transformResponse: (response: { ranking: Ranking }) => response.ranking,
      providesTags: ["JobApplicants"],
    }),
    listScreeningDecisions: build.query<ScreeningDecision[], { jobId: string } & PageParams>({
      query: ({ jobId, ...params }) => ({ url: `/employer/jobs/${jobId}/screening/decisions`, params }),
      transformResponse: (response: { decisions: ScreeningDecision[] }) => response.decisions,
    }),
    shortlistApplicants: build.mutation<{ count: number }, { jobId: string; application_ids?: string[]; threshold?: number }>({
      query: ({ jobId, ...body }) => ({ url: `/employer/jobs/${jobId}/applications/shortlist`, method: "POST", body }),
      invalidatesTags: jobApplicantTags,
    }),
    rejectApplicants: build.mutation<unknown, { jobId: string; application_ids: string[]; reason: string }>({
      query: ({ jobId, ...body }) => ({ url: `/employer/jobs/${jobId}/applications/reject`, method: "POST", body: { ...body, confirm: true } }),
      invalidatesTags: jobApplicantTags,
    }),
    getApplicant: build.query<ApplicantDetail, string>({
      query: (id) => `/employer/applications/${id}`,
      transformResponse: (response: { application: ApplicantDetail }) => response.application,
      providesTags: (_r, _e, id) => [{ type: "JobApplicants", id }],
    }),
    transitionApplicant: build.mutation<ApplicantDetail, { id: string; to: ApplicationStatus; note?: string; hr_interview_at?: string }>({
      query: ({ id, ...body }) => ({ url: `/employer/applications/${id}/transition`, method: "POST", body }),
      invalidatesTags: jobApplicantTags,
    }),
    advanceApplicant: build.mutation<ApplicantDetail, string>({
      query: (id) => ({ url: `/employer/applications/${id}/advance`, method: "POST" }),
      invalidatesTags: jobApplicantTags,
    }),
    addApplicantNote: build.mutation<unknown, { id: string; body: string }>({
      query: ({ id, body }) => ({ url: `/employer/applications/${id}/notes`, method: "POST", body: { body } }),
      invalidatesTags: (_r, _e, { id }) => [{ type: "JobApplicants", id }],
    }),
    makeOffer: build.mutation<unknown, { id: string; ctc: number; currency?: string; joining_date?: string; valid_days?: number; role_title?: string; note?: string }>({
      query: ({ id, ...body }) => ({ url: `/employer/applications/${id}/offer`, method: "POST", body }),
      invalidatesTags: jobApplicantTags,
    }),
    placeApplicant: build.mutation<ApplicantDetail, string>({
      query: (id) => ({ url: `/employer/applications/${id}/place`, method: "POST" }),
      invalidatesTags: jobApplicantTags,
    }),
  }),
});

export const {
  useListApplicantsQuery,
  useGetFunnelQuery,
  useGetRankingQuery,
  useListScreeningDecisionsQuery,
  useShortlistApplicantsMutation,
  useRejectApplicantsMutation,
  useGetApplicantQuery,
  useTransitionApplicantMutation,
  useAdvanceApplicantMutation,
  useAddApplicantNoteMutation,
  useMakeOfferMutation,
  usePlaceApplicantMutation,
} = pipelineApi;
