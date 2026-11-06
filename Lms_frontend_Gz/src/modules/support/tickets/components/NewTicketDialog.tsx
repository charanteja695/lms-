import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { toOptions } from "@/core/lib/options";
import { useListMyCoursesQuery } from "@/modules/learning/common/api/myCoursesApi";
import { AttachmentPicker } from "@/modules/support/common/components/AttachmentPicker";
import { useAttachmentUploads } from "@/modules/support/common/hooks/useAttachmentUploads";
import { CATEGORY_LABELS } from "@/modules/support/common/labels";
import type { Category, Ticket } from "@/modules/support/common/types";
import { useCreateTicketMutation } from "@/modules/support/tickets/api/myTicketsApi";
import { Button, Field, Input, Modal, Select, Textarea } from "@/shared/ui";

/** The category decides the queue server-side (learning → your institution's staff, integrity → the exam team, ...). */
export function NewTicketDialog({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: (ticket: Ticket) => void }) {
  const notify = useNotify();
  const [idempotencyKey] = useState(() => crypto.randomUUID());
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<Category>("learning");
  const [courseId, setCourseId] = useState("");
  const { data: courses = [] } = useListMyCoursesQuery(undefined, { skip: !open });
  const [create, { isLoading }] = useCreateTicketMutation();
  const uploads = useAttachmentUploads();

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New support ticket"
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            loading={isLoading}
            disabled={uploads.uploading}
            onClick={async () => {
              try {
                onCreated(await create({ idempotencyKey, body: { subject, description, category, course_id: courseId || null, attachments: uploads.refs } }).unwrap());
              } catch (error) {
                notify.apiError(error);
              }
            }}
          >
            Send
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Category" required>{(props) => <Select {...props} value={category} options={toOptions(CATEGORY_LABELS)} onChange={(event) => setCategory(event.target.value as Category)} />}</Field>
          <Field label="Course" hint="Optional — helps route it to the right people.">
            {(props) => (
              <Select {...props} value={courseId} placeholder="Not about a course" options={courses.map((course) => ({ value: course.course_id, label: course.title }))} onChange={(event) => setCourseId(event.target.value)} />
            )}
          </Field>
        </div>
        <Field label="Subject" required>{(props) => <Input {...props} value={subject} maxLength={200} onChange={(event) => setSubject(event.target.value)} />}</Field>
        <Field label="What happened?" required>{(props) => <Textarea {...props} rows={6} value={description} maxLength={8000} onChange={(event) => setDescription(event.target.value)} />}</Field>
        <AttachmentPicker uploads={uploads} disabled={isLoading} />
      </div>
    </Modal>
  );
}
