import { useFormContext, type FieldValues } from "react-hook-form";

import { Field, Textarea } from "@/shared/ui";
import { BaseFieldProps, useFieldError } from "./useFieldError";

export function TextareaField<T extends FieldValues>({ name, label, hint, required, className, rows, maxLength }: BaseFieldProps<T> & { rows?: number; maxLength?: number }) {
  const { register } = useFormContext<T>();
  const error = useFieldError(name);
  return (
    <Field label={label} hint={hint} error={error} required={required} className={className}>
      {(props) => <Textarea {...props} {...register(name)} rows={rows} maxLength={maxLength} invalid={Boolean(error)} />}
    </Field>
  );
}
