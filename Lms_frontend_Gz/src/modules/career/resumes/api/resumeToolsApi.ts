import { baseApi } from "@/core/api/baseApi";
import type { AtsResult } from "@/modules/career/resumes/types";

export interface KeywordGap {
  match_percent: number;
  keywords: { term: string; weight: number; present: boolean }[];
  add_from_profile: string[];
  not_in_profile: string[];
  advice: string;
}

export interface GrammarIssue {
  where: string;
  item_id: string | null;
  code: string;
  severity: string;
  message: string;
  excerpt: string;
}

/** An AI suggestion; `applicable: false` means it mentions something not in the student's facts (career-service checks). */
export interface Suggestion {
  text: string;
  applicable: boolean;
  warnings: { type: string; value: string }[];
  language_issues: string[];
  original?: string;
  metric_prompt?: string | null;
}

export interface Share {
  token: string;
  url_path: string;
  version_no: number;
  expires_at: string | null;
  show_contact: boolean;
}

type JobBody = { resumeId: string; job_description?: string | null };

/** Scoring, checks and AI suggestions. None of these save anything; the student applies what they keep. */
export const resumeToolsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    scoreResume: build.mutation<AtsResult, JobBody>({
      query: ({ resumeId, ...body }) => ({ url: `/resumes/${resumeId}/ats`, method: "POST", body }),
      transformResponse: (response: { ats: AtsResult }) => response.ats,
    }),
    keywordGap: build.mutation<KeywordGap, JobBody>({
      query: ({ resumeId, ...body }) => ({ url: `/resumes/${resumeId}/keyword-gap`, method: "POST", body }),
      transformResponse: (response: { ats: KeywordGap }) => response.ats,
    }),
    /** The gap is rule-based; a tailored summary (a model call) only when asked. */
    aiTailor: build.mutation<{ gap: KeywordGap; summary: Suggestion | null }, JobBody & { include_summary: boolean }>({
      query: ({ resumeId, ...body }) => ({ url: `/resumes/${resumeId}/ai/tailor`, method: "POST", body }),
      transformResponse: (response: { suggestion: { gap: KeywordGap; summary: Suggestion | null } }) => response.suggestion,
    }),
    grammarCheck: build.mutation<GrammarIssue[], string>({
      query: (resumeId) => ({ url: `/resumes/${resumeId}/grammar`, method: "POST" }),
      transformResponse: (response: { issues: GrammarIssue[] }) => response.issues,
    }),
    aiSummary: build.mutation<Suggestion, { resumeId: string; tone?: string }>({
      query: ({ resumeId, tone }) => ({ url: `/resumes/${resumeId}/ai/summary`, method: "POST", body: { tone } }),
      transformResponse: (response: { suggestion: Suggestion }) => response.suggestion,
    }),
    aiRewrite: build.mutation<Suggestion[], { resumeId: string; bullets: string[]; context?: string }>({
      query: ({ resumeId, ...body }) => ({ url: `/resumes/${resumeId}/ai/rewrite`, method: "POST", body }),
      transformResponse: (response: { suggestions: Suggestion[] }) => response.suggestions,
    }),
    aiPolish: build.mutation<Suggestion, { resumeId: string; text: string; tone?: string }>({
      query: ({ resumeId, ...body }) => ({ url: `/resumes/${resumeId}/ai/polish`, method: "POST", body }),
      transformResponse: (response: { suggestion: Suggestion }) => response.suggestion,
    }),
    shareResume: build.mutation<Share, { resumeId: string; version_no?: number; expires_in_days?: number; show_contact: boolean }>({
      query: ({ resumeId, ...body }) => ({ url: `/resumes/${resumeId}/share`, method: "POST", body }),
      transformResponse: (response: { share: Share }) => response.share,
      invalidatesTags: (_result, _error, { resumeId }) => [{ type: "Resume", id: resumeId }, "ResumeList"],
    }),
    unshareResume: build.mutation<void, string>({
      query: (resumeId) => ({ url: `/resumes/${resumeId}/share`, method: "DELETE" }),
      invalidatesTags: (_result, _error, resumeId) => [{ type: "Resume", id: resumeId }, "ResumeList"],
    }),
    /** PDF / JSON Resume need the bearer token, so they come back as bytes and are handed over as an object URL. */
    exportResume: build.mutation<string, { resumeId: string; format: "pdf" | "json-resume"; version_no?: number }>({
      query: ({ resumeId, format, version_no }) => ({
        url: `/resumes/${resumeId}/export/${format}`,
        params: version_no ? { version_no } : undefined,
        responseHandler: async (response) => (response.ok ? URL.createObjectURL(await response.blob()) : response.json()),
      }),
    }),
  }),
});

export const {
  useScoreResumeMutation,
  useKeywordGapMutation,
  useAiTailorMutation,
  useGrammarCheckMutation,
  useAiSummaryMutation,
  useAiRewriteMutation,
  useAiPolishMutation,
  useShareResumeMutation,
  useUnshareResumeMutation,
  useExportResumeMutation,
} = resumeToolsApi;
