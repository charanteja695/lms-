import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { Difficulty, Plan, PlanKind, PlanStatus, Round } from "@/modules/ai-interview/common/types";

export interface PlanBody {
  kind: PlanKind;
  title: string;
  role: string;
  skills: string[];
  difficulty: Difficulty;
  duration_minutes: number;
  rounds: Round[];
  criteria_weights?: Record<string, number> | null;
  instructions?: string | null;
  proctoring_level: string;
  max_attempts: number;
  retake_cooldown_days: number;
}

export interface CalibrationRun {
  run_id: string;
  model: string | null;
  prompt_version: number | null;
  samples: number;
  mean_abs_error: number | null;
  within_one_rate: number | null;
  recommendation_agreement: number | null;
  details: Record<string, unknown>[];
  created_at: string;
}

const planTags = (id: string) => [{ type: "InterviewPlan" as const, id }, "InterviewPlanList" as const];
type PlanResponse = { plan: Plan };

export const plansApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listPlans: build.query<ListResult<Plan>, { kind?: PlanKind; status?: PlanStatus } & PageParams>({
      query: (params) => ({ url: "/interview-plans", params }),
      transformResponse: (r: { plans: Plan[]; page_context: PageContext }) => ({ items: r.plans, pageContext: r.page_context }),
      providesTags: ["InterviewPlanList"],
    }),
    getPlan: build.query<Plan, string>({
      query: (id) => `/interview-plans/${id}`,
      transformResponse: (r: PlanResponse) => r.plan,
      providesTags: (_r, _e, id) => [{ type: "InterviewPlan", id }],
    }),
    createPlan: build.mutation<Plan, PlanBody>({
      query: (body) => ({ url: "/interview-plans", method: "POST", body }),
      transformResponse: (r: PlanResponse) => r.plan,
      invalidatesTags: ["InterviewPlanList"],
    }),
    updatePlan: build.mutation<Plan, { id: string; body: Omit<PlanBody, "kind"> }>({
      query: ({ id, body }) => ({ url: `/interview-plans/${id}`, method: "PATCH", body }),
      transformResponse: (r: PlanResponse) => r.plan,
      invalidatesTags: (_r, _e, { id }) => planTags(id),
    }),
    planAction: build.mutation<Plan, { id: string; action: "publish" | "retire" | "versions" }>({
      query: ({ id, action }) => ({ url: `/interview-plans/${id}/${action}`, method: "POST" }),
      transformResponse: (r: PlanResponse) => r.plan,
      invalidatesTags: (_r, _e, { id }) => planTags(id),
    }),
    listCalibrationSamples: build.query<{ sample_id: string; human_scores: Record<string, number>; human_recommendation: string; created_at: string }[], string>({
      query: (id) => `/interview-plans/${id}/calibration/samples`,
      transformResponse: (r: { samples: { sample_id: string; human_scores: Record<string, number>; human_recommendation: string; created_at: string }[] }) => r.samples,
      providesTags: ["Calibration"],
    }),
    listCalibrationRuns: build.query<CalibrationRun[], string>({
      query: (id) => `/interview-plans/${id}/calibration/runs`,
      transformResponse: (r: { runs: CalibrationRun[] }) => r.runs,
      providesTags: ["Calibration"],
    }),
    runCalibration: build.mutation<CalibrationRun, string>({
      query: (id) => ({ url: `/interview-plans/${id}/calibration/runs`, method: "POST" }),
      transformResponse: (r: { run: CalibrationRun }) => r.run,
      invalidatesTags: ["Calibration"],
    }),
    getPlanAudit: build.query<Record<string, unknown> & { note: string; adverse_impact: { groups?: Record<string, unknown>[]; flagged_groups?: string[]; rule?: string } }, string>({
      query: (id) => `/interview-plans/${id}/audit`,
      transformResponse: (r: { audit: Record<string, unknown> & { note: string; adverse_impact: { groups?: Record<string, unknown>[]; flagged_groups?: string[]; rule?: string } } }) => r.audit,
    }),
  }),
});

export const {
  useListPlansQuery,
  useGetPlanQuery,
  useCreatePlanMutation,
  useUpdatePlanMutation,
  usePlanActionMutation,
  useListCalibrationSamplesQuery,
  useListCalibrationRunsQuery,
  useRunCalibrationMutation,
  useGetPlanAuditQuery,
} = plansApi;
