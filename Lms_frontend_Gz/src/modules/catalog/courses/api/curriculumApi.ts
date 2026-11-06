import { baseApi } from "@/core/api/baseApi";
import type { ModuleCreateBody, ModuleUpdateBody, TopicCreateBody, TopicItem, TopicItemCreateBody, TopicItemUpdateBody, TopicUpdateBody } from "@/modules/catalog/courses/curriculumTypes";

/** Module/topic/item CRUD + reorder, within one draft version. Course + version lifecycle lives in coursesApi.ts. */
interface ModuleRef {
  courseId: string;
  versionId: string;
  moduleId: string;
}
interface TopicRef extends ModuleRef {
  topicId: string;
}
interface ItemRef extends TopicRef {
  topicItemId: string;
}

export const curriculumApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    createModule: build.mutation<{ message: string; module: { module_id: string } }, Omit<ModuleRef, "moduleId"> & { body: ModuleCreateBody }>({
      query: ({ courseId, versionId, body }) => ({ url: `/courses/${courseId}/versions/${versionId}/modules`, method: "POST", body }),
      invalidatesTags: (_result, _error, { versionId }) => [{ type: "CourseVersion", id: versionId }],
    }),
    updateModule: build.mutation<void, ModuleRef & { body: ModuleUpdateBody }>({
      query: ({ courseId, versionId, moduleId, body }) => ({ url: `/courses/${courseId}/versions/${versionId}/modules/${moduleId}`, method: "PATCH", body }),
      invalidatesTags: (_result, _error, { versionId }) => [{ type: "CourseVersion", id: versionId }],
    }),
    deleteModule: build.mutation<void, ModuleRef>({
      query: ({ courseId, versionId, moduleId }) => ({ url: `/courses/${courseId}/versions/${versionId}/modules/${moduleId}`, method: "DELETE" }),
      invalidatesTags: (_result, _error, { versionId }) => [{ type: "CourseVersion", id: versionId }],
    }),
    reorderModules: build.mutation<void, Omit<ModuleRef, "moduleId"> & { orderedIds: string[] }>({
      query: ({ courseId, versionId, orderedIds }) => ({ url: `/courses/${courseId}/versions/${versionId}/modules/reorder`, method: "PUT", body: { ordered_ids: orderedIds } }),
      invalidatesTags: (_result, _error, { versionId }) => [{ type: "CourseVersion", id: versionId }],
    }),

    createTopic: build.mutation<{ message: string; topic: { topic_id: string } }, ModuleRef & { body: TopicCreateBody }>({
      query: ({ courseId, versionId, moduleId, body }) => ({ url: `/courses/${courseId}/versions/${versionId}/modules/${moduleId}/topics`, method: "POST", body }),
      invalidatesTags: (_result, _error, { versionId }) => [{ type: "CourseVersion", id: versionId }],
    }),
    updateTopic: build.mutation<void, TopicRef & { body: TopicUpdateBody }>({
      query: ({ courseId, versionId, moduleId, topicId, body }) => ({ url: `/courses/${courseId}/versions/${versionId}/modules/${moduleId}/topics/${topicId}`, method: "PATCH", body }),
      invalidatesTags: (_result, _error, { versionId }) => [{ type: "CourseVersion", id: versionId }],
    }),
    deleteTopic: build.mutation<void, TopicRef>({
      query: ({ courseId, versionId, moduleId, topicId }) => ({ url: `/courses/${courseId}/versions/${versionId}/modules/${moduleId}/topics/${topicId}`, method: "DELETE" }),
      invalidatesTags: (_result, _error, { versionId }) => [{ type: "CourseVersion", id: versionId }],
    }),
    reorderTopics: build.mutation<void, ModuleRef & { orderedIds: string[] }>({
      query: ({ courseId, versionId, moduleId, orderedIds }) => ({ url: `/courses/${courseId}/versions/${versionId}/modules/${moduleId}/topics/reorder`, method: "PUT", body: { ordered_ids: orderedIds } }),
      invalidatesTags: (_result, _error, { versionId }) => [{ type: "CourseVersion", id: versionId }],
    }),

    createItem: build.mutation<TopicItem, TopicRef & { body: TopicItemCreateBody }>({
      query: ({ courseId, versionId, moduleId, topicId, body }) => ({
        url: `/courses/${courseId}/versions/${versionId}/modules/${moduleId}/topics/${topicId}/items`,
        method: "POST",
        body,
      }),
      transformResponse: (response: { topic_item: TopicItem }) => response.topic_item,
      invalidatesTags: (_result, _error, { versionId }) => [{ type: "CourseVersion", id: versionId }],
    }),
    updateItem: build.mutation<void, ItemRef & { body: TopicItemUpdateBody }>({
      query: ({ courseId, versionId, moduleId, topicId, topicItemId, body }) => ({
        url: `/courses/${courseId}/versions/${versionId}/modules/${moduleId}/topics/${topicId}/items/${topicItemId}`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_result, _error, { versionId }) => [{ type: "CourseVersion", id: versionId }],
    }),
    deleteItem: build.mutation<void, ItemRef>({
      query: ({ courseId, versionId, moduleId, topicId, topicItemId }) => ({
        url: `/courses/${courseId}/versions/${versionId}/modules/${moduleId}/topics/${topicId}/items/${topicItemId}`,
        method: "DELETE",
      }),
      invalidatesTags: (_result, _error, { versionId }) => [{ type: "CourseVersion", id: versionId }],
    }),
    reorderItems: build.mutation<void, TopicRef & { orderedIds: string[] }>({
      query: ({ courseId, versionId, moduleId, topicId, orderedIds }) => ({
        url: `/courses/${courseId}/versions/${versionId}/modules/${moduleId}/topics/${topicId}/items/reorder`,
        method: "PUT",
        body: { ordered_ids: orderedIds },
      }),
      invalidatesTags: (_result, _error, { versionId }) => [{ type: "CourseVersion", id: versionId }],
    }),
  }),
});

export const {
  useCreateModuleMutation,
  useUpdateModuleMutation,
  useDeleteModuleMutation,
  useReorderModulesMutation,
  useCreateTopicMutation,
  useUpdateTopicMutation,
  useDeleteTopicMutation,
  useReorderTopicsMutation,
  useCreateItemMutation,
  useUpdateItemMutation,
  useDeleteItemMutation,
  useReorderItemsMutation,
} = curriculumApi;
