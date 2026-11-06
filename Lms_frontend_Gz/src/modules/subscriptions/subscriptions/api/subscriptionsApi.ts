import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { Subscription, SubscriptionFilters } from "@/modules/subscriptions/subscriptions/types";

export const subscriptionsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listSubscriptions: build.query<ListResult<Subscription>, SubscriptionFilters & PageParams>({
      query: (params) => ({ url: "/subscriptions", params }),
      transformResponse: (response: { subscriptions: Subscription[]; page_context: PageContext }) => ({
        items: response.subscriptions,
        pageContext: response.page_context,
      }),
      providesTags: ["SubscriptionList"],
    }),
    getSubscription: build.query<Subscription, string>({
      query: (id) => `/subscriptions/${id}`,
      transformResponse: (response: { subscription: Subscription }) => response.subscription,
      providesTags: (_result, _error, id) => [{ type: "Subscription", id }],
    }),
    cancelSubscription: build.mutation<Subscription, { id: string; reason: string }>({
      query: ({ id, reason }) => ({ url: `/subscriptions/${id}/cancel`, method: "POST", body: { reason } }),
      transformResponse: (response: { subscription: Subscription }) => response.subscription,
      invalidatesTags: (_result, _error, { id }) => [{ type: "Subscription", id }, "SubscriptionList"],
    }),
  }),
});

export const { useListSubscriptionsQuery, useGetSubscriptionQuery, useCancelSubscriptionMutation } = subscriptionsApi;
