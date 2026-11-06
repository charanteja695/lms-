import { baseApi } from "@/core/api/baseApi";
import type { Invoice, OrgPlan, PlanTier } from "@/modules/billing/common/types";

/** Employer plans: buying one issues its invoice at once; paying the invoice activates the plan. */
export const billingPlansApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listPlanTiers: build.query<PlanTier[], void>({ query: () => "/employer/plans/tiers", transformResponse: (r: { tiers: PlanTier[] }) => r.tiers, providesTags: ["Prices"] }),
    listMyPlans: build.query<OrgPlan[], void>({ query: () => "/employer/plans", transformResponse: (r: { plans: OrgPlan[] }) => r.plans, providesTags: ["EmployerPlans"] }),
    purchasePlan: build.mutation<{ plan: OrgPlan; invoice: Invoice }, string>({
      query: (tier) => ({ url: `/employer/plans/${tier}/purchase`, method: "POST" }),
      invalidatesTags: ["EmployerPlans", "Invoices"],
    }),
  }),
});

export const { useListPlanTiersQuery, useListMyPlansQuery, usePurchasePlanMutation } = billingPlansApi;
