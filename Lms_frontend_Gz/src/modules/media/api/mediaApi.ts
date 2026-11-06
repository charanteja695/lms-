import { baseApi } from "@/core/api/baseApi";
import type { PageContext } from "@/core/api/types";
import { buildQueryString } from "@/core/lib/query";
import type { MediaAsset, MediaFilters, MediaSummary, Playback, UploadRequestBody, UploadTarget } from "@/modules/media/types";

/** media-service: lesson videos and PDFs. Files go straight to storage; the API only hands out signed links. */
export const mediaApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    requestUpload: build.mutation<{ asset: MediaAsset; upload: UploadTarget }, UploadRequestBody>({
      query: (body) => ({ url: "/media/uploads", method: "POST", body }),
    }),
    completeUpload: build.mutation<MediaAsset, string>({
      query: (assetId) => ({ url: `/media/${assetId}/complete`, method: "POST" }),
      transformResponse: (response: { asset: MediaAsset }) => response.asset,
    }),
    getMediaAsset: build.query<MediaAsset, string>({
      query: (assetId) => `/media/${assetId}`,
      transformResponse: (response: { asset: MediaAsset }) => response.asset,
    }),
    listMedia: build.query<{ assets: MediaAsset[]; page_context: PageContext }, MediaFilters>({
      query: (filters) => `/media?${buildQueryString({ ...filters })}`,
      providesTags: ["MediaLibrary"],
    }),
    getMediaSummary: build.query<MediaSummary, void>({
      query: () => "/media/summary",
      transformResponse: (response: { summary: MediaSummary }) => response.summary,
      providesTags: ["MediaLibrary"],
    }),
    archiveMedia: build.mutation<MediaAsset, string>({
      query: (assetId) => ({ url: `/media/${assetId}`, method: "DELETE" }),
      transformResponse: (response: { asset: MediaAsset }) => response.asset,
      invalidatesTags: ["MediaLibrary"],
    }),
    restoreMedia: build.mutation<MediaAsset, string>({
      query: (assetId) => ({ url: `/media/${assetId}/restore`, method: "POST" }),
      transformResponse: (response: { asset: MediaAsset }) => response.asset,
      invalidatesTags: ["MediaLibrary"],
    }),
    createPlayback: build.mutation<Playback, string>({
      query: (assetId) => ({ url: `/media/${assetId}/playback-tokens`, method: "POST" }),
      transformResponse: (response: { playback: Playback }) => response.playback,
    }),
  }),
});

export const {
  useRequestUploadMutation, useCompleteUploadMutation, useGetMediaAssetQuery, useCreatePlaybackMutation,
  useListMediaQuery, useGetMediaSummaryQuery, useArchiveMediaMutation, useRestoreMediaMutation,
} = mediaApi;
