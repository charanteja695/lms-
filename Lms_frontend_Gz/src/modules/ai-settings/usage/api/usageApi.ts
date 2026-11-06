import { baseApi } from "@/core/api/baseApi";
import type { Quota, QuotaBody, Usage } from "@/modules/ai-settings/common/types";

/** An organisation's AI limits and its usage in one month (YYYY-MM). The server decides who may see or change them. */
export const usageApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getAiQuota: build.query<Quota, string>({
      query: (organizationId) => `/orgs/${organizationId}/quota`,
      transformResponse: (r: { quota: Quota }) => r.quota,
      providesTags: (_r, _e, id) => [{ type: "AiQuota", id }],
    }),
    setAiQuota: build.mutation<Quota, { organizationId: string; body: QuotaBody }>({
      query: ({ organizationId, body }) => ({ url: `/orgs/${organizationId}/quota`, method: "PUT", body }),
      transformResponse: (r: { quota: Quota }) => r.quota,
      invalidatesTags: (_r, _e, { organizationId }) => [{ type: "AiQuota", id: organizationId }],
    }),
    getAiUsage: build.query<Usage, { organizationId: string; period: string }>({
      query: ({ organizationId, period }) => ({ url: `/orgs/${organizationId}/usage`, params: { period } }),
      transformResponse: (r: { usage: Usage }) => r.usage,
      providesTags: (_r, _e, { organizationId }) => [{ type: "AiQuota", id: organizationId }],
    }),
  }),
});

export const { useGetAiQuotaQuery, useSetAiQuotaMutation, useGetAiUsageQuery } = usageApi;
