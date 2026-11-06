import { baseApi } from "@/core/api/baseApi";
import type { OptionsHook } from "@/shared/ui";

/**
 * The company's own published hiring tests (assessment-service) and screening interview plans (ai-interview-service)
 * a job's pipeline can name — this module's own reads of those services (rule 5).
 */
export const stagePickersApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listHiringTests: build.query<{ test_id: string; title: string }[], string>({
      query: (search) => ({ url: "/tests", params: { kind: "hiring", status: "published", search: search || undefined, per_page: 20 } }),
      transformResponse: (response: { tests: { test_id: string; title: string }[] }) => response.tests,
    }),
    listScreeningPlans: build.query<{ plan_id: string; title: string; role: string | null }[], void>({
      query: () => ({ url: "/interview-plans", params: { kind: "screening", status: "published", per_page: 100 } }),
      transformResponse: (response: { plans: { plan_id: string; title: string; role: string | null }[] }) => response.plans,
    }),
  }),
});

const { useListHiringTestsQuery, useListScreeningPlansQuery } = stagePickersApi;

export const useHiringTestOptions: OptionsHook = (search, enabled) => {
  const { data = [], isFetching } = useListHiringTestsQuery(search, { skip: !enabled });
  return { isFetching, options: data.map((test) => ({ value: test.test_id, label: test.title })) };
};

export const useScreeningPlanOptions: OptionsHook = (search, enabled) => {
  const { data = [], isFetching } = useListScreeningPlansQuery(undefined, { skip: !enabled });
  const term = search.toLowerCase();
  return {
    isFetching,
    options: data.filter((plan) => !term || plan.title.toLowerCase().includes(term)).map((plan) => ({ value: plan.plan_id, label: plan.title, description: plan.role ?? undefined })),
  };
};
