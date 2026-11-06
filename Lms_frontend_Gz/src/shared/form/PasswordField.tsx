import { useFormContext, type FieldValues } from "react-hook-form";

import { Field, PasswordInput } from "@/shared/ui";
import { BaseFieldProps, useFieldError } from "./useFieldError";

export function PasswordField<T extends FieldValues>({ name, label, hint, required, className, autoComplete = "current-password" }: BaseFieldProps<T> & { autoComplete?: string }) {
  const { register } = useFormContext<T>();
  const error = useFieldError(name);
  return (
    <Field label={label} hint={hint} error={error} required={required} className={className}>
      {(props) => <PasswordInput {...props} {...register(name)} invalid={Boolean(error)} autoComplete={autoComplete} maxLength={128} />}
    </Field>
  );
}
