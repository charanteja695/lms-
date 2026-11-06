import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { Quote, QuoteStatus } from "@/modules/billing/common/types";

const one = (r: { quote: Quote }) => r.quote;
const tags = (id: string) => [{ type: "Quotes" as const, id }, "Quotes" as const];

/** Course-seat quotes: a head asks, a billing manager may discount, the head accepts (which fixes the price, nothing more). */
export const quotesApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listQuotes: build.query<ListResult<Quote>, { status?: QuoteStatus; organization_id?: string } & PageParams>({
      query: (params) => ({ url: "/quotes", params }),
      transformResponse: (r: { quotes: Quote[]; page_context: PageContext }) => ({ items: r.quotes, pageContext: r.page_context }),
      providesTags: ["Quotes"],
    }),
    getQuote: build.query<Quote, string>({ query: (id) => `/quotes/${id}`, transformResponse: one, providesTags: (_r, _e, id) => [{ type: "Quotes", id }] }),
    createQuote: build.mutation<Quote, { organization_id?: string; lines: { course_id: string; seats: number; term_days: number }[] }>({
      query: (body) => ({ url: "/quotes", method: "POST", body }),
      transformResponse: one,
      invalidatesTags: ["Quotes"],
    }),
    acceptQuote: build.mutation<Quote, string>({ query: (id) => ({ url: `/quotes/${id}/accept`, method: "POST" }), transformResponse: one, invalidatesTags: (_r, _e, id) => tags(id) }),
    cancelQuote: build.mutation<Quote, string>({ query: (id) => ({ url: `/quotes/${id}/cancel`, method: "POST" }), transformResponse: one, invalidatesTags: (_r, _e, id) => tags(id) }),
    discountQuote: build.mutation<Quote, { id: string; amount: number; note: string }>({
      query: ({ id, ...body }) => ({ url: `/admin/quotes/${id}/discount`, method: "POST", body }),
      transformResponse: one,
      invalidatesTags: (_r, _e, { id }) => tags(id),
    }),
  }),
});

export const { useListQuotesQuery, useGetQuoteQuery, useCreateQuoteMutation, useAcceptQuoteMutation, useCancelQuoteMutation, useDiscountQuoteMutation } = quotesApi;
