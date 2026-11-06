import { useFormContext, type FieldValues } from "react-hook-form";

import { Field, type Option, Select } from "@/shared/ui";
import { BaseFieldProps, useFieldError } from "./useFieldError";

export function SelectField<T extends FieldValues>({ name, label, hint, required, className, options, placeholder, disabled }: BaseFieldProps<T> & {
  options: readonly Option[];
  placeholder?: string;
}) {
  const { register } = useFormContext<T>();
  const error = useFieldError(name);
  return (
    <Field label={label} hint={hint} error={error} required={required} className={className}>
      {(props) => <Select {...props} {...register(name)} options={options} placeholder={placeholder} invalid={Boolean(error)} disabled={disabled} />}
    </Field>
  );
}
