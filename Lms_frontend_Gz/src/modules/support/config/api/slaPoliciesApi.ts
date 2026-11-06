import { baseApi } from "@/core/api/baseApi";
import type { Priority, Queue } from "@/modules/support/common/types";

export interface SlaPolicy {
  queue: Queue;
  priority: Priority;
  first_response_minutes: number;
  resolution_minutes: number;
  is_default: boolean;
}

/** Support managers: one row per queue × priority; a change applies to tickets created or re-prioritised from then on. */
export const slaPoliciesApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listSlaPolicies: build.query<SlaPolicy[], void>({
      query: () => "/admin/sla-policies",
      transformResponse: (response: { policies: SlaPolicy[] }) => response.policies,
      providesTags: ["SlaPolicies"],
    }),
    saveSlaPolicy: build.mutation<SlaPolicy[], Omit<SlaPolicy, "is_default">>({
      query: (body) => ({ url: "/admin/sla-policies", method: "PUT", body }),
      transformResponse: (response: { policies: SlaPolicy[] }) => response.policies,
      invalidatesTags: ["SlaPolicies"],
    }),
    resetSlaPolicy: build.mutation<SlaPolicy[], { queue: Queue; priority: Priority }>({
      query: ({ queue, priority }) => ({ url: `/admin/sla-policies/${queue}/${priority}`, method: "DELETE" }),
      transformResponse: (response: { policies: SlaPolicy[] }) => response.policies,
      invalidatesTags: ["SlaPolicies"],
    }),
  }),
});

export const { useListSlaPoliciesQuery, useSaveSlaPolicyMutation, useResetSlaPolicyMutation } = slaPoliciesApi;
