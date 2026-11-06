import { useState, type ReactNode } from "react";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { NameDialog } from "@/modules/catalog/builder/components/NameDialog";
import { LessonUploadModal } from "@/modules/catalog/builder/components/upload/LessonUploadModal";
import { ModuleMediaUploadModal } from "@/modules/catalog/builder/components/upload/ModuleMediaUploadModal";
import type { UploadKind } from "@/modules/catalog/builder/hooks/useLessonUploads";
import {
  useCreateModuleMutation,
  useCreateTopicMutation,
  useDeleteItemMutation,
  useDeleteModuleMutation,
  useDeleteTopicMutation,
  useReorderItemsMutation,
  useReorderModulesMutation,
  useReorderTopicsMutation,
  useUpdateItemMutation,
  useUpdateModuleMutation,
  useUpdateTopicMutation,
} from "@/modules/catalog/courses/api/curriculumApi";
import type { CourseVersionDetail, ModuleDetail, TopicDetail, TopicItem } from "@/modules/catalog/courses/curriculumTypes";
import { ConfirmDialog } from "@/shared/ui";

/** Moves one id a step up (-1) or down (+1) in a list of ids. */
function moved(ids: string[], id: string, step: -1 | 1): string[] | null {
  const from = ids.indexOf(id);
  const to = from + step;
  if (from < 0 || to < 0 || to >= ids.length) return null;
  const next = ids.filter((other) => other !== id);
  next.splice(to, 0, id);
  return next;
}

export type CurriculumActions = ReturnType<typeof useCurriculumActions>["actions"];

/** Every edit the builder offers, with its dialogs. Returns the handlers and the dialogs to render once. */
export function useCurriculumActions(courseId: string, versionId: string, version: CourseVersionDetail | undefined) {
  const notify = useNotify();
  const confirm = useConfirmAction();
  const [dialog, setDialog] = useState<ReactNode>(null);
  const close = () => setDialog(null);
  const ref = { courseId, versionId };

  const [createModule] = useCreateModuleMutation();
  const [updateModule] = useUpdateModuleMutation();
  const [deleteModule] = useDeleteModuleMutation();
  const [reorderModules] = useReorderModulesMutation();
  const [createTopic] = useCreateTopicMutation();
  const [updateTopic] = useUpdateTopicMutation();
  const [deleteTopic] = useDeleteTopicMutation();
  const [reorderTopics] = useReorderTopicsMutation();
  const [updateItem] = useUpdateItemMutation();
  const [deleteItem] = useDeleteItemMutation();
  const [reorderItems] = useReorderItemsMutation();

  const guarded = (work: () => Promise<unknown>, failure: string) => work().catch((error) => notify.apiError(error, failure));
  const named = (heading: string, label: string, submitLabel: string, onSubmit: (name: string) => Promise<unknown>, initial?: string, placeholder?: string) =>
    setDialog(<NameDialog heading={heading} label={label} submitLabel={submitLabel} initial={initial} placeholder={placeholder} onSubmit={onSubmit} onClose={close} />);
  const removing = (title: string, description: string, work: () => Promise<unknown>) =>
    confirm.ask({ title, description, confirmLabel: "Delete" }, async () => {
      await guarded(work, "Could not delete");
    });

  const actions = {
    addModule: () => named("Add module", "Module title", "Add module", (title) => createModule({ ...ref, body: { title } }).unwrap(), "", "e.g. Python basics"),
    renameModule: (module: ModuleDetail) => named("Rename module", "Module title", "Save", (title) => updateModule({ ...ref, moduleId: module.module_id, body: { title } }).unwrap(), module.title),
    deleteModule: (module: ModuleDetail) =>
      removing(`Delete “${module.title}”?`, "Its topics and lessons are removed from this draft.", () => deleteModule({ ...ref, moduleId: module.module_id }).unwrap()),
    moveModule: (module: ModuleDetail, step: -1 | 1) => {
      const order = moved((version?.modules ?? []).map((m) => m.module_id), module.module_id, step);
      if (order) void guarded(() => reorderModules({ ...ref, orderedIds: order }).unwrap(), "Could not move the module");
    },

    addTopic: (module: ModuleDetail) =>
      named("Add topic", "Topic title", "Add topic", (title) => createTopic({ ...ref, moduleId: module.module_id, body: { title } }).unwrap(), "", "e.g. Variables and data types"),
    renameTopic: (module: ModuleDetail, topic: TopicDetail) =>
      named("Rename topic", "Topic title", "Save", (title) => updateTopic({ ...ref, moduleId: module.module_id, topicId: topic.topic_id, body: { title } }).unwrap(), topic.title),
    deleteTopic: (module: ModuleDetail, topic: TopicDetail) =>
      removing(`Delete “${topic.title}”?`, "Its lessons are removed from this draft. Its test stays in the question bank.", () => deleteTopic({ ...ref, moduleId: module.module_id, topicId: topic.topic_id }).unwrap()),
    moveTopic: (module: ModuleDetail, topic: TopicDetail, step: -1 | 1) => {
      const order = moved(module.topics.map((t) => t.topic_id), topic.topic_id, step);
      if (order) void guarded(() => reorderTopics({ ...ref, moduleId: module.module_id, orderedIds: order }).unwrap(), "Could not move the topic");
    },

    uploadToModule: (module: ModuleDetail, kind: UploadKind = "video", moduleNumber?: number) =>
      setDialog(
        <ModuleMediaUploadModal
          courseId={courseId}
          versionId={versionId}
          module={module}
          moduleNumber={moduleNumber}
          initialKind={kind}
          onClose={close}
        />
      ),

    upload: (module: ModuleDetail, topic: TopicDetail, kind: UploadKind, label: string) =>
      setDialog(<LessonUploadModal topic={{ ...ref, moduleId: module.module_id, topicId: topic.topic_id }} topicLabel={label} initialKind={kind} onClose={close} />),
    renameLesson: (module: ModuleDetail, topic: TopicDetail, item: TopicItem) =>
      named("Rename lesson", "Lesson title", "Save", (title) => updateItem({ ...ref, moduleId: module.module_id, topicId: topic.topic_id, topicItemId: item.topic_item_id, body: { title } }).unwrap(), item.title),
    deleteLesson: (module: ModuleDetail, topic: TopicDetail, item: TopicItem) =>
      removing(`Delete “${item.title}”?`, "The lesson is removed from this draft.", () => deleteItem({ ...ref, moduleId: module.module_id, topicId: topic.topic_id, topicItemId: item.topic_item_id }).unwrap()),
    moveLesson: (module: ModuleDetail, topic: TopicDetail, item: TopicItem, step: -1 | 1) => {
      const order = moved(topic.items.map((i) => i.topic_item_id), item.topic_item_id, step);
      if (order) void guarded(() => reorderItems({ ...ref, moduleId: module.module_id, topicId: topic.topic_id, orderedIds: order }).unwrap(), "Could not move the lesson");
    },
  };

  const dialogs = (
    <>
      {dialog}
      <ConfirmDialog {...confirm.dialogProps} />
    </>
  );
  return { actions, dialogs };
}
