import { baseApi } from "@/core/api/baseApi";
import type { Category, Preference } from "@/modules/notifications/common/types";

/** Per category, whether a notification is also emailed. In-app is always on. */
export const preferencesApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getPreferences: build.query<Preference[], void>({
      query: () => "/notification-preferences",
      transformResponse: (r: { preferences: Preference[] }) => r.preferences,
      providesTags: ["NotificationPreferences"],
    }),
    updatePreferences: build.mutation<Preference[], { category: Category; email_enabled: boolean }[]>({
      query: (preferences) => ({ url: "/notification-preferences", method: "PUT", body: { preferences } }),
      transformResponse: (r: { preferences: Preference[] }) => r.preferences,
      invalidatesTags: ["NotificationPreferences"],
    }),
  }),
});

export const { useGetPreferencesQuery, useUpdatePreferencesMutation } = preferencesApi;
