import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { FaqCreateBody, FaqEntry, FaqManageFilters } from "@/modules/ai-tutor/faq/types";

type FaqResponse = { faq: FaqEntry };

export const faqApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    /** What a student sees: published entries from the platform, their institution and their courses. */
    listStudentFaq: build.query<FaqEntry[], { q?: string; course_id?: string }>({
      query: (params) => ({ url: "/faq", params }),
      transformResponse: (response: { faqs: FaqEntry[] }) => response.faqs,
      providesTags: ["TutorFaqList"],
    }),
    listManageableFaq: build.query<ListResult<FaqEntry>, FaqManageFilters & PageParams>({
      query: (params) => ({ url: "/faq/manage", params }),
      transformResponse: (response: { faqs: FaqEntry[]; page_context: PageContext }) => ({ items: response.faqs, pageContext: response.page_context }),
      providesTags: ["TutorFaqList"],
    }),
    createFaq: build.mutation<FaqEntry, FaqCreateBody>({
      query: (body) => ({ url: "/faq/manage", method: "POST", body }),
      transformResponse: (response: FaqResponse) => response.faq,
      invalidatesTags: ["TutorFaqList"],
    }),
    updateFaq: build.mutation<FaqEntry, { faqId: string; question: string; answer: string }>({
      query: ({ faqId, question, answer }) => ({ url: `/faq/manage/${faqId}`, method: "PATCH", body: { question, answer } }),
      transformResponse: (response: FaqResponse) => response.faq,
      invalidatesTags: ["TutorFaqList"],
    }),
    publishFaq: build.mutation<FaqEntry, string>({
      query: (faqId) => ({ url: `/faq/manage/${faqId}/publish`, method: "POST" }),
      transformResponse: (response: FaqResponse) => response.faq,
      invalidatesTags: ["TutorFaqList"],
    }),
    archiveFaq: build.mutation<FaqEntry, string>({
      query: (faqId) => ({ url: `/faq/manage/${faqId}/archive`, method: "POST" }),
      transformResponse: (response: FaqResponse) => response.faq,
      invalidatesTags: ["TutorFaqList"],
    }),
  }),
});

export const {
  useListStudentFaqQuery,
  useListManageableFaqQuery,
  useCreateFaqMutation,
  useUpdateFaqMutation,
  usePublishFaqMutation,
  useArchiveFaqMutation,
} = faqApi;
