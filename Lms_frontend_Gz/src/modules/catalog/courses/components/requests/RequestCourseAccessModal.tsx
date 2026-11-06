import { useNotify } from "@/core/hooks/useNotify";
import type { Course } from "@/modules/catalog/courses/types";
import { useSubmitCourseRequestMutation } from "@/modules/subscriptions/course-requests/api/courseRequestsApi";
import { Button, Modal } from "@/shared/ui";

interface RequestCourseAccessModalProps {
  open: boolean;
  onClose: () => void;
  course: Course | null;
  onSuccess?: () => void;
}

export function RequestCourseAccessModal({
  open,
  onClose,
  course,
  onSuccess,
}: RequestCourseAccessModalProps) {
  const notify = useNotify();
  const [submitRequest, { isLoading }] = useSubmitCourseRequestMutation();

  if (!course) return null;

  const handleConfirm = async () => {
    try {
      await submitRequest({
        course_id: course.course_id,
        requested_seats: 100,
        requested_term_days: 365,
      }).unwrap();
      notify.success("Course access request submitted successfully.");
      onSuccess?.();
      onClose();
    } catch (err) {
      notify.apiError(err, "Failed to submit course access request");
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Request Course Access"
      description={`Confirm access request for "${course.title}" for your institution.`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handleConfirm}
            loading={isLoading}
            className="bg-blue-600 hover:bg-blue-700 text-white font-medium"
          >
            Confirm Request
          </Button>
        </>
      }
    >
      <div className="space-y-4 py-1">
        <div className="rounded-xl border border-blue-100 bg-blue-50/60 p-3.5">
          <p className="text-xs font-semibold text-blue-900 mb-1">Course Selected</p>
          <h4 className="text-base font-bold text-slate-900">{course.title}</h4>
          {course.summary && (
            <p className="mt-1 line-clamp-2 text-xs text-slate-600">{course.summary}</p>
          )}
        </div>

        <p className="text-sm text-slate-600">
          Are you sure you want to request course access for your institution? Once submitted, platform administrators will review your request.
        </p>
      </div>
    </Modal>
  );
}
