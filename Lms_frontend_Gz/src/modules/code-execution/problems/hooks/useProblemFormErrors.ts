import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { applyServerErrors, toApiError } from "@/core/lib/apiError";
import type { ProblemFormValues } from "@/modules/code-execution/problems/form/problemForm";
import { isProblemField } from "@/modules/code-execution/problems/form/problemForm";

export function useProblemFormErrors() {
  const [formError, setFormError] = useState<string | null>(null);
  const notify = useNotify();
  const handle = (error: unknown, setError: Parameters<typeof applyServerErrors<ProblemFormValues>>[1]) => {
    const apiError = toApiError(error);
    const unmatched = applyServerErrors(apiError, setError, isProblemField);
    if (!apiError.details.length || unmatched.length) setFormError(apiError.message);
    else {
      setFormError(null);
      notify.error(apiError.message, "Check the highlighted fields.");
    }
  };
  return { formError, setFormError, handle };
}
