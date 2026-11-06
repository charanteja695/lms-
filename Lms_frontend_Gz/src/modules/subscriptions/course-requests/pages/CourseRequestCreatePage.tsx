import { useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useSubmitCourseRequestMutation } from "@/modules/subscriptions/course-requests/api/courseRequestsApi";
import { CourseRequestForm } from "@/modules/subscriptions/course-requests/components/form/CourseRequestForm";
import { emptyCourseRequestForm, toCourseRequestCreateBody } from "@/modules/subscriptions/course-requests/form/courseRequestForm";
import { useCourseRequestFormErrors } from "@/modules/subscriptions/course-requests/hooks/useCourseRequestFormErrors";
import { PageHeader } from "@/shared/ui";

export function CourseRequestCreatePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const notify = useNotify();
  const [submit, { isLoading }] = useSubmitCourseRequestMutation();
  const { formError, setFormError, handle } = useCourseRequestFormErrors();
  const courseIdParam = searchParams.get("course_id") ?? "";
  const defaults = useMemo(
    () => ({
      ...emptyCourseRequestForm(),
      course_id: courseIdParam,
    }),
    [courseIdParam],
  );

  return (
    <>
      <PageHeader title="New course request" backTo="/course-requests" backLabel="Course requests" />
      <CourseRequestForm
        defaultValues={defaults}
        submitting={isLoading}
        formError={formError}
        onCancel={() => navigate("/course-requests")}
        onSubmit={async (values, form) => {
          setFormError(null);
          try {
            await submit(toCourseRequestCreateBody(values)).unwrap();
            notify.success("Course request submitted", "An admin will review it.");
            navigate("/course-requests", { replace: true });
          } catch (error) {
            handle(error, form.setError);
          }
        }}
      />
    </>
  );
}
