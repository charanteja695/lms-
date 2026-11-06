import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { Delivery, DeliveryStatus, Template } from "@/modules/notifications/common/types";

/** Super admin only: template wording per type and channel, and the email delivery log. */
export const notificationAdminApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listNotificationTemplates: build.query<Template[], void>({
      query: () => "/notification-templates",
      transformResponse: (r: { templates: Template[] }) => r.templates,
      providesTags: ["NotificationTemplates"],
    }),
    saveTemplate: build.mutation<Template, { type: string; channel: string; subject: string; body: string }>({
      query: ({ type, channel, ...body }) => ({ url: `/notification-templates/${type}/${channel}`, method: "PUT", body }),
      invalidatesTags: ["NotificationTemplates"],
    }),
    resetTemplate: build.mutation<Template, { type: string; channel: string }>({
      query: ({ type, channel }) => ({ url: `/notification-templates/${type}/${channel}`, method: "DELETE" }),
      invalidatesTags: ["NotificationTemplates"],
    }),
    listDeliveries: build.query<ListResult<Delivery>, { status?: DeliveryStatus } & PageParams>({
      query: (params) => ({ url: "/deliveries", params }),
      transformResponse: (r: { deliveries: Delivery[]; page_context: PageContext }) => ({ items: r.deliveries, pageContext: r.page_context }),
      providesTags: ["Deliveries"],
    }),
    retryDelivery: build.mutation<Delivery, string>({
      query: (id) => ({ url: `/deliveries/${id}/retry`, method: "POST" }),
      invalidatesTags: ["Deliveries"],
    }),
  }),
});

export const { useListNotificationTemplatesQuery, useSaveTemplateMutation, useResetTemplateMutation, useListDeliveriesQuery, useRetryDeliveryMutation } = notificationAdminApi;
