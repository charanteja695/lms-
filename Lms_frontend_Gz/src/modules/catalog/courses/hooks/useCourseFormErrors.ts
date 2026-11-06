import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { applyServerErrors, toApiError } from "@/core/lib/apiError";
import type { CourseFormValues } from "@/modules/catalog/courses/form/courseForm";
import { isCourseField } from "@/modules/catalog/courses/form/courseForm";

export function useCourseFormErrors() {
  const [formError, setFormError] = useState<string | null>(null);
  const notify = useNotify();
  const handle = (error: unknown, setError: Parameters<typeof applyServerErrors<CourseFormValues>>[1]) => {
    const apiError = toApiError(error);
    const unmatched = applyServerErrors(apiError, setError, isCourseField);
    if (!apiError.details.length || unmatched.length) setFormError(apiError.message);
    else {
      setFormError(null);
      notify.error(apiError.message, "Check the highlighted fields.");
    }
  };
  return { formError, setFormError, handle };
}
