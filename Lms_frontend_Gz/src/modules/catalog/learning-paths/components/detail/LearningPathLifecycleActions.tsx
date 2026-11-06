import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { useArchiveLearningPathMutation, usePublishLearningPathMutation } from "@/modules/catalog/learning-paths/api/learningPathsApi";
import type { LearningPath } from "@/modules/catalog/learning-paths/types";
import { Button, ConfirmDialog } from "@/shared/ui";

/** Publish/archive, shown only when the path's status and the viewer's scope allow it. */
export function LearningPathLifecycleActions({ path, canAuthor }: { path: LearningPath; canAuthor: boolean }) {
  const notify = useNotify();
  const confirm = useConfirmAction();
  const [publish, { isLoading: publishing }] = usePublishLearningPathMutation();
  const [archive, { isLoading: archiving }] = useArchiveLearningPathMutation();

  if (!canAuthor) return null;

  const run = async (work: () => Promise<unknown>, success: string) => {
    try {
      await work();
      notify.success(success);
    } catch (error) {
      notify.apiError(error);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      {path.status === "draft" && (
        <Button
          icon="upload"
          loading={publishing}
          onClick={() =>
            confirm.ask(
              { title: "Publish this learning path?", description: "Learners can enrol in it once published.", confirmLabel: "Publish", tone: "primary" },
              () => run(() => publish(path.learning_path_id).unwrap(), "Learning path published"),
            )
          }
        >
          Publish
        </Button>
      )}
      {path.status === "published" && (
        <Button
          variant="secondary"
          icon="archive"
          loading={archiving}
          onClick={() =>
            confirm.ask(
              { title: "Archive this learning path?", description: "It stops being offered to new learners.", confirmLabel: "Archive" },
              () => run(() => archive(path.learning_path_id).unwrap(), "Learning path archived"),
            )
          }
        >
          Archive
        </Button>
      )}
      <ConfirmDialog {...confirm.dialogProps} />
    </div>
  );
}
