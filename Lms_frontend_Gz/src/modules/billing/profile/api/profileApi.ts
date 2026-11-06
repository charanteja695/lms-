import { baseApi } from "@/core/api/baseApi";
import type { BillingProfile, BillingProfileInput } from "@/modules/billing/common/types";

const out = (r: { profile: BillingProfile }) => r.profile;

/** The legal details a GST invoice needs. A contact edits their own; a billing manager edits any organisation's. */
export const profileApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getMyBillingProfile: build.query<BillingProfile, void>({ query: () => "/billing-profile", transformResponse: out, providesTags: [{ type: "BillingProfile", id: "mine" }] }),
    saveMyBillingProfile: build.mutation<BillingProfile, BillingProfileInput>({
      query: (body) => ({ url: "/billing-profile", method: "PUT", body }),
      transformResponse: out,
      invalidatesTags: [{ type: "BillingProfile", id: "mine" }, "Quotes"],
    }),
    getOrgBillingProfile: build.query<BillingProfile, string>({
      query: (orgId) => `/admin/organizations/${orgId}/billing-profile`,
      transformResponse: out,
      providesTags: (_r, _e, id) => [{ type: "BillingProfile", id }],
    }),
    saveOrgBillingProfile: build.mutation<BillingProfile, { orgId: string } & BillingProfileInput>({
      query: ({ orgId, ...body }) => ({ url: `/admin/organizations/${orgId}/billing-profile`, method: "PUT", body }),
      transformResponse: out,
      invalidatesTags: (_r, _e, { orgId }) => [{ type: "BillingProfile", id: orgId }],
    }),
  }),
});

export const { useGetMyBillingProfileQuery, useSaveMyBillingProfileMutation, useGetOrgBillingProfileQuery, useSaveOrgBillingProfileMutation } = profileApi;
