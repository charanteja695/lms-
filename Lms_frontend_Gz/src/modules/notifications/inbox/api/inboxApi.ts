import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { Notification } from "@/modules/notifications/common/types";

/** The signed-in person's in-app notifications; the server only ever returns their own. */
export const inboxApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listNotifications: build.query<ListResult<Notification>, { unread?: boolean } & PageParams>({
      query: (params) => ({ url: "/notifications", params }),
      transformResponse: (r: { notifications: Notification[]; page_context: PageContext }) => ({ items: r.notifications, pageContext: r.page_context }),
      providesTags: ["Notifications"],
    }),
    getUnreadCount: build.query<number, void>({
      query: () => "/notifications/unread-count",
      transformResponse: (r: { unread_count: number }) => r.unread_count,
      providesTags: ["UnreadCount"],
    }),
    markRead: build.mutation<Notification, string>({
      query: (id) => ({ url: `/notifications/${id}/read`, method: "POST" }),
      invalidatesTags: ["Notifications", "UnreadCount"],
    }),
    markAllRead: build.mutation<number, void>({
      query: () => ({ url: "/notifications/read-all", method: "POST" }),
      transformResponse: (r: { updated_count: number }) => r.updated_count,
      invalidatesTags: ["Notifications", "UnreadCount"],
    }),
  }),
});

export const { useListNotificationsQuery, useGetUnreadCountQuery, useMarkReadMutation, useMarkAllReadMutation } = inboxApi;
