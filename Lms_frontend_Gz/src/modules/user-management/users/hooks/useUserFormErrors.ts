import { useNotify } from "@/core/hooks/useNotify";
import { applyServerErrors, toApiError } from "@/core/lib/apiError";
import type { UserFormProps } from "@/modules/user-management/users/components/form/UserForm";
import { isFormField } from "@/modules/user-management/users/form/userFormFields";

export type SubmitHandler = UserFormProps["onSubmit"];

export function useServerErrorHandler(setFormError: (message: string | null) => void) {
  const notify = useNotify();
  return (error: unknown, form: Parameters<SubmitHandler>[1]) => {
    const apiError = toApiError(error);
    const unmatched = applyServerErrors(apiError, form.setError, isFormField);
    if (!apiError.details.length || unmatched.length) {
      setFormError(unmatched.length ? `${apiError.message} ${unmatched.map((detail) => detail.message).join(". ")}` : apiError.message);
    } else {
      setFormError(null);
      notify.error(apiError.message, "Check the highlighted fields.");
    }
  };
}
