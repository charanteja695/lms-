import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useAddCourseToPathMutation } from "@/modules/catalog/learning-paths/api/learningPathsApi";
import { useCourseOptions } from "@/modules/catalog/common/hooks/useCourseOptions";
import { Button, EntityPicker, Modal } from "@/shared/ui";

export function AddCourseDialog({ open, onClose, learningPathId }: { open: boolean; onClose: () => void; learningPathId: string }) {
  const notify = useNotify();
  const [addCourse, { isLoading }] = useAddCourseToPathMutation();
  const [courseId, setCourseId] = useState("");
  const [courseLabel, setCourseLabel] = useState("");

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add a course"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            loading={isLoading}
            disabled={!courseId}
            onClick={async () => {
              try {
                await addCourse({ id: learningPathId, courseId }).unwrap();
                notify.success("Course added");
                onClose();
              } catch (error) {
                notify.apiError(error);
              }
            }}
          >
            Add course
          </Button>
        </>
      }
    >
      <EntityPicker label="Course" value={courseId} selectedLabel={courseLabel} useOptions={useCourseOptions} onChange={(value, label) => { setCourseId(value); setCourseLabel(label); }} />
    </Modal>
  );
}
