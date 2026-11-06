import { baseApi } from "@/core/api/baseApi";

export interface PresignedPost {
  url: string;
  fields: Record<string, string>;
}

/** Upload URLs and short-lived download links for ticket attachments. Type and size limits are the server's. */
export const attachmentsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getAttachmentUploadUrl: build.mutation<{ key: string; upload: PresignedPost }, { filename: string; content_type: string; size_bytes: number }>({
      query: (body) => ({ url: "/attachments/upload-url", method: "POST", body }),
      transformResponse: (response: { attachment: { key: string; upload: PresignedPost } }) => response.attachment,
    }),
    /** `ticketPath` is `/tickets/{id}` for the requester or `/agent/tickets/{id}` for an agent. */
    getAttachmentLink: build.mutation<{ filename: string; url: string }, { ticketPath: string; messageId: string; index: number }>({
      query: ({ ticketPath, messageId, index }) => ({ url: `${ticketPath}/messages/${messageId}/attachments/${index}`, method: "GET" }),
      transformResponse: (response: { attachment: { filename: string; url: string } }) => response.attachment,
    }),
  }),
});

export const { useGetAttachmentUploadUrlMutation, useGetAttachmentLinkMutation } = attachmentsApi;
