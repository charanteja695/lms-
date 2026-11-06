import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { Batch, BatchCreateBody, BatchFilters } from "@/modules/learning/batches/types";

export const batchesApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listBatches: build.query<ListResult<Batch>, BatchFilters & PageParams>({
      query: (params) => ({ url: "/batches", params }),
      transformResponse: (response: { batches: Batch[]; page_context: PageContext }) => ({
        items: response.batches,
        pageContext: response.page_context,
      }),
      providesTags: ["BatchList"],
    }),
    getBatch: build.query<Batch, string>({
      query: (id) => `/batches/${id}`,
      transformResponse: (response: { batch: Batch }) => response.batch,
      providesTags: (_result, _error, id) => [{ type: "Batch", id }],
    }),
    createBatch: build.mutation<Batch, BatchCreateBody>({
      query: (body) => ({ url: "/batches", method: "POST", body }),
      transformResponse: (response: { batch: Batch }) => response.batch,
      invalidatesTags: ["BatchList"],
    }),
  }),
});

export const { useListBatchesQuery, useGetBatchQuery, useCreateBatchMutation } = batchesApi;
