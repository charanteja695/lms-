import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { Appeal, Interview, Turn } from "@/modules/ai-interview/common/types";

export interface ScreeningInterview extends Interview {
  application_id: string | null;
  job_id: string | null;
  user_id: string;
  integrity_status: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  final_recommendation: string | null;
  review_note: string | null;
}

export interface Evaluation {
  status: string;
  model: string | null;
  prompt_version: number | null;
  rounds: { round?: string; comment?: string; scores?: Record<string, { score: number; evidence?: { quote: string; valid?: boolean }[] }> }[];
  criterion_scores: Record<string, number>;
  overall_score: number | null;
  recommendation: string | null;
  summary: string | null;
  strengths: string[];
  improvements: string[];
  flags: string[];
  invalid_quotes: number;
  total_quotes: number;
  last_error: string | null;
}

export interface ScreeningDetail extends ScreeningInterview {
  transcript: Turn[];
  evaluation: Evaluation | null;
}

const tags = (id: string) => [{ type: "ScreeningInterview" as const, id }, "ScreeningInterview" as const];

/** A company's screening interviews. Only a person's review makes a result visible to the candidate. */
export const screeningApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listScreeningInterviews: build.query<ListResult<ScreeningInterview>, { status?: string; job_id?: string } & PageParams>({
      query: (params) => ({ url: "/employer/interviews", params }),
      transformResponse: (r: { interviews: ScreeningInterview[]; page_context: PageContext }) => ({ items: r.interviews, pageContext: r.page_context }),
      providesTags: ["ScreeningInterview"],
    }),
    getScreeningInterview: build.query<ScreeningDetail, string>({
      query: (id) => `/employer/interviews/${id}`,
      transformResponse: (r: { interview: ScreeningDetail }) => r.interview,
      providesTags: (_r, _e, id) => [{ type: "ScreeningInterview", id }],
    }),
    reviewInterview: build.mutation<ScreeningInterview, { id: string; recommendation?: string; note?: string; release_feedback: boolean }>({
      query: ({ id, ...body }) => ({ url: `/employer/interviews/${id}/review`, method: "POST", body }),
      invalidatesTags: (_r, _e, { id }) => tags(id),
    }),
    reEvaluate: build.mutation<ScreeningInterview, string>({
      query: (id) => ({ url: `/employer/interviews/${id}/evaluate`, method: "POST" }),
      invalidatesTags: (_r, _e, id) => tags(id),
    }),
    listOpenAppeals: build.query<ListResult<Appeal & { interview: ScreeningInterview }>, PageParams>({
      query: (params) => ({ url: "/employer/appeals", params }),
      transformResponse: (r: { appeals: (Appeal & { interview: ScreeningInterview })[]; page_context: PageContext }) => ({ items: r.appeals, pageContext: r.page_context }),
      providesTags: ["InterviewAppeals"],
    }),
    decideAppeal: build.mutation<Appeal, { interviewId: string; uphold: boolean; note?: string }>({
      query: ({ interviewId, ...body }) => ({ url: `/employer/interviews/${interviewId}/appeal/decide`, method: "POST", body }),
      invalidatesTags: ["InterviewAppeals", "ScreeningInterview"],
    }),
    addCalibrationSample: build.mutation<unknown, { planId: string; turns: Turn[]; human_scores: Record<string, number>; human_recommendation: string }>({
      query: ({ planId, turns, ...body }) => ({
        url: `/interview-plans/${planId}/calibration/samples`,
        method: "POST",
        body: { ...body, turns: turns.map(({ seq, round, speaker, kind, text, elapsed_ms }) => ({ seq, round, speaker, kind, text, elapsed_ms })) },
      }),
      invalidatesTags: ["Calibration"],
    }),
  }),
});

export const {
  useListScreeningInterviewsQuery,
  useGetScreeningInterviewQuery,
  useReviewInterviewMutation,
  useReEvaluateMutation,
  useListOpenAppealsQuery,
  useDecideAppealMutation,
  useAddCalibrationSampleMutation,
} = screeningApi;
