import { baseApi } from "@/core/api/baseApi";
import type { Capability, ModelRoutes, RouteEntry } from "@/modules/ai-settings/common/types";

/** The order in which AI providers are tried, per capability (the first that answers wins). */
export const modelsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getModelRoutes: build.query<ModelRoutes, void>({
      query: () => "/models",
      transformResponse: (r: { models: ModelRoutes }) => r.models,
      providesTags: ["AiModels"],
    }),
    setModelRoute: build.mutation<RouteEntry[], { capability: Capability; providers: RouteEntry[] }>({
      query: ({ capability, providers }) => ({ url: `/models/${capability}`, method: "PATCH", body: { providers } }),
      transformResponse: (r: { providers: RouteEntry[] }) => r.providers,
      invalidatesTags: ["AiModels"],
    }),
  }),
});

export const { useGetModelRoutesQuery, useSetModelRouteMutation } = modelsApi;
