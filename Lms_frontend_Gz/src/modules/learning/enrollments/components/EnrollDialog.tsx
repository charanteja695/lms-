import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useEnrollStudentMutation } from "@/modules/learning/enrollments/api/enrollmentsApi";
import { useStudentOptions } from "@/modules/learning/enrollments/hooks/useStudentOptions";
import { Button, EntityPicker, Modal } from "@/shared/ui";

export function EnrollDialog({ open, onClose, batchId, organizationId }: { open: boolean; onClose: () => void; batchId: string; organizationId: string }) {
  const notify = useNotify();
  const [enroll, { isLoading }] = useEnrollStudentMutation();
  const [studentId, setStudentId] = useState("");
  const [studentLabel, setStudentLabel] = useState("");
  const useOptions = useStudentOptions(organizationId);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Enrol a student"
      description="Reserves a seat on this batch's subscription."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            loading={isLoading}
            disabled={!studentId}
            onClick={async () => {
              try {
                await enroll({ batchId, body: { student_user_id: studentId } }).unwrap();
                notify.success("Student enrolled");
                onClose();
              } catch (error) {
                notify.apiError(error);
              }
            }}
          >
            Enrol
          </Button>
        </>
      }
    >
      <EntityPicker label="Student" value={studentId} selectedLabel={studentLabel} useOptions={useOptions} onChange={(value, label) => { setStudentId(value); setStudentLabel(label); }} />
    </Modal>
  );
}
