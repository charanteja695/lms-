import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { applyServerErrors, toApiError } from "@/core/lib/apiError";
import type { CourseRequestFormValues } from "@/modules/subscriptions/course-requests/form/courseRequestForm";
import { isCourseRequestField } from "@/modules/subscriptions/course-requests/form/courseRequestForm";

export function useCourseRequestFormErrors() {
  const [formError, setFormError] = useState<string | null>(null);
  const notify = useNotify();
  const handle = (error: unknown, setError: Parameters<typeof applyServerErrors<CourseRequestFormValues>>[1]) => {
    const apiError = toApiError(error);
    const unmatched = applyServerErrors(apiError, setError, isCourseRequestField);
    if (!apiError.details.length || unmatched.length) setFormError(apiError.message);
    else {
      setFormError(null);
      notify.error(apiError.message, "Check the highlighted fields.");
    }
  };
  return { formError, setFormError, handle };
}
