import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { Appeal, Interview, Plan, RoundType, Turn } from "@/modules/ai-interview/common/types";

export interface TurnPair {
  turn: Turn;
  reply: Turn | null;
  finished: boolean;
  degraded: boolean;
  audio: string | null;
  audio_type: string | null;
  audio_error: string | null;
}

export interface Report {
  released: boolean;
  summary: string | null;
  criterion_scores: Record<string, number>;
  strengths: string[];
  improvements: string[];
  improvement_plan: string | null;
  overall_score: number | null;
  /** Scores run from 1 to this. */
  score_max: number;
  /** Per round: its score, the AI's comment, and the candidate's own words the scores rest on. */
  rounds: { round: string; type: RoundType; score: number | null; comment: string; quotes: string[] }[];
}

const base = (id: string) => `/student/interviews/${id}`;
const tags = (id: string) => [{ type: "MyInterview" as const, id }, "MyInterviewList" as const];

/** The candidate's side. The server owns the clock (`ends_at`) and chooses every question; the page only shows and sends. */
export const studentInterviewsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listMockPlans: build.query<Plan[], void>({
      query: () => ({ url: "/student/mock-plans", params: { per_page: 50 } }),
      transformResponse: (r: { plans: Plan[] }) => r.plans,
    }),
    listMyInterviews: build.query<ListResult<Interview>, { status?: string; kind?: string } & PageParams>({
      query: (params) => ({ url: "/student/interviews", params }),
      transformResponse: (r: { interviews: Interview[]; page_context: PageContext }) => ({ items: r.interviews, pageContext: r.page_context }),
      providesTags: ["MyInterviewList"],
    }),
    getMyInterview: build.query<Interview, string>({
      query: (id) => base(id),
      transformResponse: (r: { interview: Interview }) => r.interview,
      providesTags: (_r, _e, id) => [{ type: "MyInterview", id }],
    }),
    getMyTranscript: build.query<Turn[], string>({
      query: (id) => `${base(id)}/transcript`,
      transformResponse: (r: { turns: Turn[] }) => r.turns,
      providesTags: (_r, _e, id) => [{ type: "MyInterview", id }],
    }),
    startMock: build.mutation<Interview, string>({
      query: (plan_id) => ({ url: "/student/interviews", method: "POST", body: { plan_id } }),
      transformResponse: (r: { interview: Interview }) => r.interview,
      invalidatesTags: ["MyInterviewList"],
    }),
    getConsent: build.query<{ version: string; text: string; recording_required: boolean; instructions: string | null }, string>({
      query: (id) => `${base(id)}/consent`,
      transformResponse: (r: { consent: { version: string; text: string; recording_required: boolean; instructions: string | null } }) => r.consent,
    }),
    giveConsent: build.mutation<Interview, { id: string; version: string; recording: boolean }>({
      query: ({ id, ...body }) => ({ url: `${base(id)}/consent`, method: "POST", body }),
      invalidatesTags: (_r, _e, { id }) => tags(id),
    }),
    startInterview: build.mutation<TurnPair, string>({
      query: (id) => ({ url: `${base(id)}/start`, method: "POST" }),
      transformResponse: (r: { turns: TurnPair }) => r.turns,
      invalidatesTags: (_r, _e, id) => tags(id),
    }),
    answerTurn: build.mutation<TurnPair, { id: string; text: string; want_audio?: boolean; key: string }>({
      query: ({ id, key, ...body }) => ({ url: `${base(id)}/turns`, method: "POST", body, headers: { "Idempotency-Key": key } }),
      transformResponse: (r: { turns: TurnPair }) => r.turns,
    }),
    answerTurnAudio: build.mutation<TurnPair, { id: string; audio: Blob; want_audio: boolean; key: string }>({
      query: ({ id, audio, want_audio, key }) => {
        const form = new FormData();
        form.append("audio", audio, "answer.webm");
        form.append("want_audio", String(want_audio));
        return { url: `${base(id)}/turns/audio`, method: "POST", body: form, headers: { "Idempotency-Key": key } };
      },
      transformResponse: (r: { turns: TurnPair }) => r.turns,
    }),
    runInterviewCode: build.mutation<{ status: string; outcome: string | null; stdout: string; stderr: string; compile_output: string; time_ms: number | null }, { id: string; language: string; source: string; stdin?: string }>({
      query: ({ id, ...body }) => ({ url: `${base(id)}/code/run`, method: "POST", body }),
      transformResponse: (r: { run: { status: string; outcome: string | null; stdout: string; stderr: string; compile_output: string; time_ms: number | null } }) => r.run,
    }),
    getTimeLeft: build.query<{ round_seconds_left: number; interview_seconds_left: number }, string>({
      query: (id) => `${base(id)}/time-left`,
    }),
    endInterview: build.mutation<Interview, string>({
      query: (id) => ({ url: `${base(id)}/end`, method: "POST" }),
      invalidatesTags: (_r, _e, id) => tags(id),
    }),
    getMyReport: build.query<Report, string>({
      query: (id) => `${base(id)}/report`,
      transformResponse: (r: { report: Report }) => r.report,
      providesTags: (_r, _e, id) => [{ type: "MyInterview", id }],
    }),
    appealInterview: build.mutation<Appeal, { id: string; reason: string }>({
      query: ({ id, reason }) => ({ url: `${base(id)}/appeal`, method: "POST", body: { reason } }),
      transformResponse: (r: { appeal: Appeal }) => r.appeal,
      invalidatesTags: (_r, _e, { id }) => tags(id),
    }),
    retakeInterview: build.mutation<Interview, string>({
      query: (id) => ({ url: `${base(id)}/retake`, method: "POST" }),
      transformResponse: (r: { interview: Interview }) => r.interview,
      invalidatesTags: ["MyInterviewList"],
    }),
  }),
});

export const {
  useListMockPlansQuery,
  useListMyInterviewsQuery,
  useGetMyInterviewQuery,
  useGetMyTranscriptQuery,
  useStartMockMutation,
  useGetConsentQuery,
  useGiveConsentMutation,
  useStartInterviewMutation,
  useAnswerTurnMutation,
  useAnswerTurnAudioMutation,
  useRunInterviewCodeMutation,
  useGetTimeLeftQuery,
  useEndInterviewMutation,
  useGetMyReportQuery,
  useAppealInterviewMutation,
  useRetakeInterviewMutation,
} = studentInterviewsApi;
