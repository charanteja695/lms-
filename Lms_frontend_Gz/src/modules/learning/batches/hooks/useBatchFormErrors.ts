import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { applyServerErrors, toApiError } from "@/core/lib/apiError";
import type { BatchFormValues } from "@/modules/learning/batches/form/batchForm";
import { isBatchField } from "@/modules/learning/batches/form/batchForm";

export function useBatchFormErrors() {
  const [formError, setFormError] = useState<string | null>(null);
  const notify = useNotify();
  const handle = (error: unknown, setError: Parameters<typeof applyServerErrors<BatchFormValues>>[1]) => {
    const apiError = toApiError(error);
    const unmatched = applyServerErrors(apiError, setError, isBatchField);
    if (!apiError.details.length || unmatched.length) setFormError(apiError.message);
    else {
      setFormError(null);
      notify.error(apiError.message, "Check the highlighted fields.");
    }
  };
  return { formError, setFormError, handle };
}
