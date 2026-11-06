import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type {
  Enrollment,
  EnrollmentCreateBody,
  EnrollmentFilters,
  UnlockState,
} from "@/modules/learning/enrollments/types";

export const enrollmentsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listEnrollments: build.query<ListResult<Enrollment>, EnrollmentFilters & PageParams>({
      query: (params) => ({ url: "/enrollments", params }),
      transformResponse: (response: { enrollments: Enrollment[]; page_context: PageContext }) => ({
        items: response.enrollments,
        pageContext: response.page_context,
      }),
      providesTags: (result) =>
        result
          ? [...result.items.map((item) => ({ type: "Enrollment" as const, id: item.enrollment_id })), "EnrollmentList"]
          : ["EnrollmentList"],
    }),
    getEnrollment: build.query<Enrollment, string>({
      query: (id) => `/enrollments/${id}`,
      transformResponse: (response: { enrollment: Enrollment }) => response.enrollment,
      providesTags: (_result, _error, id) => [{ type: "Enrollment", id }],
    }),
    enrollStudent: build.mutation<Enrollment, { batchId: string; body: EnrollmentCreateBody }>({
      query: ({ batchId, body }) => ({ url: `/batches/${batchId}/enrollments`, method: "POST", body }),
      transformResponse: (response: { enrollment: Enrollment }) => response.enrollment,
      invalidatesTags: ["EnrollmentList"],
    }),
    withdrawEnrollment: build.mutation<Enrollment, string>({
      query: (id) => ({ url: `/enrollments/${id}/withdraw`, method: "POST" }),
      transformResponse: (response: { enrollment: Enrollment }) => response.enrollment,
      invalidatesTags: (_result, _error, id) => [{ type: "Enrollment", id }, "EnrollmentList"],
    }),
    getUnlockState: build.query<UnlockState, string>({
      query: (enrollmentId) => `/enrollments/${enrollmentId}/unlock-state`,
      transformResponse: (response: { unlock_state: UnlockState }) => response.unlock_state,
      providesTags: (_result, _error, id) => [{ type: "UnlockState", id }],
    }),
    completeItem: build.mutation<void, { enrollmentId: string; topicItemId: string }>({
      query: ({ enrollmentId, topicItemId }) => ({ url: `/enrollments/${enrollmentId}/items/${topicItemId}/complete`, method: "POST" }),
      invalidatesTags: (_result, _error, { enrollmentId }) => [{ type: "UnlockState", id: enrollmentId }],
    }),
  }),
});

export const {
  useListEnrollmentsQuery,
  useGetEnrollmentQuery,
  useEnrollStudentMutation,
  useWithdrawEnrollmentMutation,
  useGetUnlockStateQuery,
  useCompleteItemMutation,
} = enrollmentsApi;
