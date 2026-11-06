import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useCreateConversationMutation } from "@/modules/ai-tutor/chat/api/chatApi";
import { useListMyCoursesQuery } from "@/modules/learning/common/api/myCoursesApi";
import type { Conversation } from "@/modules/ai-tutor/chat/types";
import type { ConversationMode } from "@/modules/ai-tutor/common/types";
import { Button, Field, Modal, Select } from "@/shared/ui";

const MODE_OPTIONS = [
  { value: "learning", label: "Learning — questions about a course" },
  { value: "support", label: "Support — help with the platform" },
];

export function NewConversationDialog({ open, initialCourseId, onClose, onCreated }: {
  open: boolean;
  initialCourseId: string | null;
  onClose: () => void;
  onCreated: (conversation: Conversation) => void;
}) {
  const notify = useNotify();
  const [mode, setMode] = useState<ConversationMode>("learning");
  const [courseId, setCourseId] = useState(initialCourseId ?? "");
  const { data: courses = [], isFetching } = useListMyCoursesQuery(undefined, { skip: !open });
  const [create, { isLoading }] = useCreateConversationMutation();

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New conversation"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            loading={isLoading}
            disabled={mode === "learning" && !courseId}
            onClick={async () => {
              try {
                onCreated(await create({ mode, course_id: mode === "learning" ? courseId : null }).unwrap());
              } catch (error) {
                notify.apiError(error);
              }
            }}
          >
            Start
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Kind">{(props) => <Select {...props} options={MODE_OPTIONS} value={mode} onChange={(event) => setMode(event.target.value as ConversationMode)} />}</Field>
        {mode === "learning" && (
          <Field label="Course" required hint={!isFetching && courses.length === 0 ? "You're not enrolled in any active course." : undefined}>
            {(props) => (
              <Select
                {...props}
                options={courses.map((course) => ({ value: course.course_id, label: course.title }))}
                placeholder={isFetching ? "Loading…" : "Choose a course"}
                value={courseId}
                onChange={(event) => setCourseId(event.target.value)}
              />
            )}
          </Field>
        )}
      </div>
    </Modal>
  );
}
