import { baseApi } from "@/core/api/baseApi";
import type { Price, PriceKind } from "@/modules/billing/common/types";

const list = (r: { prices: Price[] }) => r.prices;

/** Active prices for anyone in billing; every price (and edits) for billing managers. Existing quotes and invoices keep the amount they used. */
export const pricesApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listActivePrices: build.query<Price[], PriceKind | void>({
      query: (kind) => ({ url: "/prices", params: { kind: kind || undefined, per_page: 100 } }),
      transformResponse: list,
      providesTags: ["Prices"],
    }),
    listAllPrices: build.query<Price[], PriceKind | void>({
      query: (kind) => ({ url: "/admin/prices", params: { kind: kind || undefined, per_page: 100 } }),
      transformResponse: list,
      providesTags: ["Prices"],
    }),
    createPrice: build.mutation<Price, { kind: PriceKind; code: string; name: string; unit_amount: number; job_posts?: number; valid_days?: number }>({
      query: (body) => ({ url: "/admin/prices", method: "POST", body }),
      invalidatesTags: ["Prices"],
    }),
    updatePrice: build.mutation<Price, { id: string; name?: string; unit_amount?: number; active?: boolean; valid_days?: number }>({
      query: ({ id, ...body }) => ({ url: `/admin/prices/${id}`, method: "PATCH", body }),
      invalidatesTags: ["Prices"],
    }),
  }),
});

export const { useListActivePricesQuery, useListAllPricesQuery, useCreatePriceMutation, useUpdatePriceMutation } = pricesApi;
