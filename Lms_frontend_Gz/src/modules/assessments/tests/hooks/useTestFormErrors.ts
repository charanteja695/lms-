import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { applyServerErrors, toApiError } from "@/core/lib/apiError";
import type { TestFormValues } from "@/modules/assessments/tests/form/testForm";
import { isTestField } from "@/modules/assessments/tests/form/testForm";

export function useTestFormErrors() {
  const [formError, setFormError] = useState<string | null>(null);
  const notify = useNotify();
  const handle = (error: unknown, setError: Parameters<typeof applyServerErrors<TestFormValues>>[1]) => {
    const apiError = toApiError(error);
    const unmatched = applyServerErrors(apiError, setError, isTestField);
    if (!apiError.details.length || unmatched.length) setFormError(apiError.message);
    else {
      setFormError(null);
      notify.error(apiError.message, "Check the highlighted fields.");
    }
  };
  return { formError, setFormError, handle };
}
