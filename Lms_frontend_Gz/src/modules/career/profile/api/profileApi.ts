import { baseApi } from "@/core/api/baseApi";
import type { ItemKind } from "@/modules/career/common/types";
import type { CareerProfile, ImportResult, ProfileItem, ProfileUpdateBody } from "@/modules/career/profile/types";

export const profileApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getMyCareerProfile: build.query<CareerProfile, void>({
      query: () => "/profile",
      providesTags: ["CareerProfile"],
    }),
    /** Read-only, for institution staff (their students) and careers managers. */
    getStudentCareerProfile: build.query<CareerProfile, string>({
      query: (userId) => `/students/${userId}/profile`,
    }),
    updateCareerProfile: build.mutation<CareerProfile, ProfileUpdateBody>({
      query: (body) => ({ url: "/profile", method: "PATCH", body }),
      invalidatesTags: ["CareerProfile"],
    }),
    addProfileItem: build.mutation<ProfileItem, { kind: ItemKind; data: Record<string, unknown> }>({
      query: (body) => ({ url: "/profile/items", method: "POST", body }),
      transformResponse: (response: { item: ProfileItem }) => response.item,
      invalidatesTags: ["CareerProfile", "Resume"],
    }),
    updateProfileItem: build.mutation<ProfileItem, { itemId: string; data: Record<string, unknown> }>({
      query: ({ itemId, data }) => ({ url: `/profile/items/${itemId}`, method: "PATCH", body: { data } }),
      transformResponse: (response: { item: ProfileItem }) => response.item,
      invalidatesTags: ["CareerProfile", "Resume"],
    }),
    deleteProfileItem: build.mutation<void, string>({
      query: (itemId) => ({ url: `/profile/items/${itemId}`, method: "DELETE" }),
      invalidatesTags: ["CareerProfile", "Resume"],
    }),
    /** An old resume or LinkedIn PDF read into proposed entries; nothing is saved until `addProfileItems`. */
    importResumeFile: build.mutation<ImportResult, File>({
      query: (file) => {
        const form = new FormData();
        form.append("file", file);
        return { url: "/profile/import", method: "POST", body: form };
      },
    }),
    addProfileItems: build.mutation<ProfileItem[], { kind: ItemKind; data: Record<string, unknown> }[]>({
      query: (items) => ({ url: "/profile/items/bulk", method: "POST", body: { items } }),
      transformResponse: (response: { items: ProfileItem[] }) => response.items,
      invalidatesTags: ["CareerProfile", "Resume"],
    }),
    reorderProfileItems: build.mutation<void, { kind: ItemKind; item_ids: string[] }>({
      query: (body) => ({ url: "/profile/items/order", method: "PUT", body }),
      invalidatesTags: ["CareerProfile"],
    }),
  }),
});

export const {
  useGetMyCareerProfileQuery,
  useGetStudentCareerProfileQuery,
  useUpdateCareerProfileMutation,
  useAddProfileItemMutation,
  useUpdateProfileItemMutation,
  useDeleteProfileItemMutation,
  useReorderProfileItemsMutation,
  useImportResumeFileMutation,
  useAddProfileItemsMutation,
} = profileApi;
