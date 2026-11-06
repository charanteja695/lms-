import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { CourseRule, CourseRuleUpdateBody, CourseVersionDetail } from "@/modules/catalog/courses/curriculumTypes";
import type { Course, CourseCreateBody, CourseFilters, CourseUpdateBody, CourseVersionOut, Review } from "@/modules/catalog/courses/types";

/** The course + its version lifecycle (publish/approve/reject/retire). Module/topic/item CRUD lives in curriculumApi.ts. */
interface VersionRef {
  courseId: string;
  versionId: string;
}

export const coursesApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listCourses: build.query<ListResult<Course>, CourseFilters & PageParams>({
      query: (params) => {
        const cleanParams: Record<string, unknown> = {};
        if (params.page) cleanParams.page = params.page;
        if (params.per_page) cleanParams.per_page = params.per_page;
        if (params.search_text && params.search_text.trim().length >= 2) {
          cleanParams.search_text = params.search_text.trim();
        }
        if (params.sort_order) cleanParams.sort_order = params.sort_order;
        if (typeof params.include_archived === "boolean") cleanParams.include_archived = params.include_archived;
        if (typeof params.published_only === "boolean") cleanParams.published_only = params.published_only;
        return { url: "/courses", params: cleanParams };
      },
      transformResponse: (response: { courses: Course[]; page_context: PageContext }) => ({
        items: response.courses,
        pageContext: response.page_context,
      }),
      providesTags: ["CourseList"],
    }),
    getCourse: build.query<Course, string>({
      query: (courseId) => `/courses/${courseId}`,
      transformResponse: (response: { course: Course }) => response.course,
      providesTags: (_result, _error, id) => [{ type: "Course", id }],
    }),
    createCourse: build.mutation<Course, CourseCreateBody>({
      query: (body) => ({ url: "/courses", method: "POST", body }),
      transformResponse: (response: { course: Course }) => response.course,
      invalidatesTags: ["CourseList"],
    }),
    updateCourse: build.mutation<Course, { courseId: string; body: CourseUpdateBody }>({
      query: ({ courseId, body }) => ({ url: `/courses/${courseId}`, method: "PATCH", body }),
      transformResponse: (response: { course: Course }) => response.course,
      invalidatesTags: (_result, _error, { courseId }) => [{ type: "Course", id: courseId }, "CourseList"],
    }),
    deleteCourse: build.mutation<void, string>({
      query: (courseId) => ({ url: `/courses/${courseId}`, method: "DELETE" }),
      invalidatesTags: ["CourseList"],
    }),
    bulkDeleteCourses: build.mutation<
      { message: string; deleted_count: number; affected_courses: string[] },
      { course_ids?: string[]; clear_all_active?: boolean }
    >({
      query: (body) => ({ url: "/courses/bulk-delete", method: "POST", body }),
      invalidatesTags: ["CourseList"],
    }),
    getCleanupSummary: build.query<
      {
        active_courses_count: number;
        published_courses_count: number;
        draft_courses_count: number;
        total_modules_count: number;
        total_chapters_count: number;
      },
      void
    >({
      query: () => "/courses/cleanup-summary",
      providesTags: ["CourseList"],
    }),
    publishCourse: build.mutation<Course, string>({
      query: (courseId) => ({ url: `/courses/${courseId}/publish`, method: "POST" }),
      transformResponse: (response: { course: Course }) => response.course,
      invalidatesTags: (_result, _error, courseId) => [{ type: "Course", id: courseId }, "CourseList"],
    }),
    unpublishCourse: build.mutation<Course, string>({
      query: (courseId) => ({ url: `/courses/${courseId}/unpublish`, method: "POST" }),
      transformResponse: (response: { course: Course }) => response.course,
      invalidatesTags: (_result, _error, courseId) => [{ type: "Course", id: courseId }, "CourseList"],
    }),

    createDraftVersion: build.mutation<CourseVersionOut, string>({
      query: (courseId) => ({ url: `/courses/${courseId}/versions`, method: "POST" }),
      transformResponse: (response: { version: CourseVersionOut }) => response.version,
      invalidatesTags: (_result, _error, courseId) => [{ type: "Course", id: courseId }],
    }),
    getVersion: build.query<CourseVersionDetail, VersionRef>({
      query: ({ courseId, versionId }) => `/courses/${courseId}/versions/${versionId}`,
      transformResponse: (response: { version: CourseVersionDetail }) => response.version,
      providesTags: (_result, _error, { versionId }) => [{ type: "CourseVersion", id: versionId }],
    }),
    updateRules: build.mutation<CourseRule, VersionRef & { body: CourseRuleUpdateBody }>({
      query: ({ courseId, versionId, body }) => ({ url: `/courses/${courseId}/versions/${versionId}/rules`, method: "PATCH", body }),
      invalidatesTags: (_result, _error, { versionId }) => [{ type: "CourseVersion", id: versionId }],
    }),
    submitVersion: build.mutation<CourseVersionOut, VersionRef>({
      query: ({ courseId, versionId }) => ({ url: `/courses/${courseId}/versions/${versionId}/submit`, method: "POST" }),
      transformResponse: (response: { version: CourseVersionOut }) => response.version,
      invalidatesTags: (_result, _error, { courseId, versionId }) => [{ type: "Course", id: courseId }, { type: "CourseVersion", id: versionId }],
    }),
    approveVersion: build.mutation<CourseVersionOut, VersionRef>({
      query: ({ courseId, versionId }) => ({ url: `/courses/${courseId}/versions/${versionId}/approve`, method: "POST" }),
      transformResponse: (response: { version: CourseVersionOut }) => response.version,
      invalidatesTags: (_result, _error, { courseId, versionId }) => [{ type: "Course", id: courseId }, { type: "CourseVersion", id: versionId }],
    }),
    rejectVersion: build.mutation<CourseVersionOut, VersionRef & { reason: string }>({
      query: ({ courseId, versionId, reason }) => ({ url: `/courses/${courseId}/versions/${versionId}/reject`, method: "POST", body: { reason } }),
      transformResponse: (response: { version: CourseVersionOut }) => response.version,
      invalidatesTags: (_result, _error, { courseId, versionId }) => [{ type: "Course", id: courseId }, { type: "CourseVersion", id: versionId }],
    }),
    retireVersion: build.mutation<CourseVersionOut, VersionRef>({
      query: ({ courseId, versionId }) => ({ url: `/courses/${courseId}/versions/${versionId}/retire`, method: "POST" }),
      transformResponse: (response: { version: CourseVersionOut }) => response.version,
      invalidatesTags: (_result, _error, { courseId, versionId }) => [{ type: "Course", id: courseId }, { type: "CourseVersion", id: versionId }],
    }),
    listReviews: build.query<Review[], VersionRef>({
      query: ({ courseId, versionId }) => `/courses/${courseId}/versions/${versionId}/reviews`,
      transformResponse: (response: { reviews: Review[] }) => response.reviews,
      providesTags: (_result, _error, { versionId }) => [{ type: "CourseVersion", id: `${versionId}-reviews` }],
    }),
  }),
});

export const {
  useListCoursesQuery,
  useGetCourseQuery,
  useCreateCourseMutation,
  useUpdateCourseMutation,
  useDeleteCourseMutation,
  useBulkDeleteCoursesMutation,
  useGetCleanupSummaryQuery,
  usePublishCourseMutation,
  useUnpublishCourseMutation,
  useCreateDraftVersionMutation,
  useGetVersionQuery,
  useUpdateRulesMutation,
  useSubmitVersionMutation,
  useApproveVersionMutation,
  useRejectVersionMutation,
  useRetireVersionMutation,
  useListReviewsQuery,
} = coursesApi;
