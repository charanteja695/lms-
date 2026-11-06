import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { ApproveRequestBody, CourseRequest, CourseRequestCreateBody, CourseRequestFilters } from "@/modules/subscriptions/course-requests/types";
import type { Subscription } from "@/modules/subscriptions/subscriptions/types";

export const courseRequestsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listCourseRequests: build.query<ListResult<CourseRequest>, CourseRequestFilters & PageParams>({
      query: (params) => ({ url: "/course-requests", params }),
      transformResponse: (response: { course_requests: CourseRequest[]; page_context: PageContext }) => ({
        items: response.course_requests,
        pageContext: response.page_context,
      }),
      providesTags: ["CourseRequestList"],
    }),
    getCourseRequest: build.query<CourseRequest, string>({
      query: (id) => `/course-requests/${id}`,
      transformResponse: (response: { course_request: CourseRequest }) => response.course_request,
      providesTags: (_result, _error, id) => [{ type: "CourseRequest", id }],
    }),
    submitCourseRequest: build.mutation<CourseRequest, CourseRequestCreateBody>({
      query: (body) => ({ url: "/course-requests", method: "POST", body }),
      transformResponse: (response: { course_request: CourseRequest }) => response.course_request,
      invalidatesTags: ["CourseRequestList"],
    }),
    approveCourseRequest: build.mutation<Subscription, { id: string; body: ApproveRequestBody }>({
      query: ({ id, body }) => ({ url: `/course-requests/${id}/approve`, method: "POST", body }),
      transformResponse: (response: { subscription: Subscription }) => response.subscription,
      invalidatesTags: (_result, _error, { id }) => [{ type: "CourseRequest", id }, "CourseRequestList", "SubscriptionList"],
    }),
    rejectCourseRequest: build.mutation<CourseRequest, { id: string; reason: string }>({
      query: ({ id, reason }) => ({ url: `/course-requests/${id}/reject`, method: "POST", body: { reason } }),
      transformResponse: (response: { course_request: CourseRequest }) => response.course_request,
      invalidatesTags: (_result, _error, { id }) => [{ type: "CourseRequest", id }, "CourseRequestList"],
    }),
  }),
});

export const {
  useListCourseRequestsQuery,
  useGetCourseRequestQuery,
  useSubmitCourseRequestMutation,
  useApproveCourseRequestMutation,
  useRejectCourseRequestMutation,
} = courseRequestsApi;
