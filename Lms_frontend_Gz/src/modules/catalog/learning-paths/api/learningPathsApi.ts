import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { LearningPath, LearningPathCreateBody, LearningPathFilters, LearningPathUpdateBody } from "@/modules/catalog/learning-paths/types";

export const learningPathsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listLearningPaths: build.query<ListResult<LearningPath>, LearningPathFilters & PageParams>({
      query: (params) => ({ url: "/learning-paths", params }),
      transformResponse: (response: { learning_paths: LearningPath[]; page_context: PageContext }) => ({
        items: response.learning_paths,
        pageContext: response.page_context,
      }),
      providesTags: ["LearningPathList"],
    }),
    getLearningPath: build.query<LearningPath, string>({
      query: (id) => `/learning-paths/${id}`,
      transformResponse: (response: { learning_path: LearningPath }) => response.learning_path,
      providesTags: (_result, _error, id) => [{ type: "LearningPath", id }],
    }),
    createLearningPath: build.mutation<LearningPath, LearningPathCreateBody>({
      query: (body) => ({ url: "/learning-paths", method: "POST", body }),
      transformResponse: (response: { learning_path: LearningPath }) => response.learning_path,
      invalidatesTags: ["LearningPathList"],
    }),
    updateLearningPath: build.mutation<LearningPath, { id: string; body: LearningPathUpdateBody }>({
      query: ({ id, body }) => ({ url: `/learning-paths/${id}`, method: "PATCH", body }),
      transformResponse: (response: { learning_path: LearningPath }) => response.learning_path,
      invalidatesTags: (_result, _error, { id }) => [{ type: "LearningPath", id }, "LearningPathList"],
    }),
    addCourseToPath: build.mutation<LearningPath, { id: string; courseId: string }>({
      query: ({ id, courseId }) => ({ url: `/learning-paths/${id}/courses`, method: "POST", body: { course_id: courseId } }),
      transformResponse: (response: { learning_path: LearningPath }) => response.learning_path,
      invalidatesTags: (_result, _error, { id }) => [{ type: "LearningPath", id }],
    }),
    removeCourseFromPath: build.mutation<LearningPath, { id: string; courseId: string }>({
      query: ({ id, courseId }) => ({ url: `/learning-paths/${id}/courses/${courseId}`, method: "DELETE" }),
      transformResponse: (response: { learning_path: LearningPath }) => response.learning_path,
      invalidatesTags: (_result, _error, { id }) => [{ type: "LearningPath", id }],
    }),
    reorderPathCourses: build.mutation<LearningPath, { id: string; orderedIds: string[] }>({
      query: ({ id, orderedIds }) => ({ url: `/learning-paths/${id}/courses/reorder`, method: "PUT", body: { ordered_ids: orderedIds } }),
      transformResponse: (response: { learning_path: LearningPath }) => response.learning_path,
      invalidatesTags: (_result, _error, { id }) => [{ type: "LearningPath", id }],
    }),
    publishLearningPath: build.mutation<LearningPath, string>({
      query: (id) => ({ url: `/learning-paths/${id}/publish`, method: "POST" }),
      transformResponse: (response: { learning_path: LearningPath }) => response.learning_path,
      invalidatesTags: (_result, _error, id) => [{ type: "LearningPath", id }, "LearningPathList"],
    }),
    archiveLearningPath: build.mutation<LearningPath, string>({
      query: (id) => ({ url: `/learning-paths/${id}/archive`, method: "POST" }),
      transformResponse: (response: { learning_path: LearningPath }) => response.learning_path,
      invalidatesTags: (_result, _error, id) => [{ type: "LearningPath", id }, "LearningPathList"],
    }),
  }),
});

export const {
  useListLearningPathsQuery,
  useGetLearningPathQuery,
  useCreateLearningPathMutation,
  useUpdateLearningPathMutation,
  useAddCourseToPathMutation,
  useRemoveCourseFromPathMutation,
  useReorderPathCoursesMutation,
  usePublishLearningPathMutation,
  useArchiveLearningPathMutation,
} = learningPathsApi;
