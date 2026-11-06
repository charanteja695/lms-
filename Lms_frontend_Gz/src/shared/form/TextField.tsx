import { useFormContext, type FieldValues } from "react-hook-form";

import { Field, Input } from "@/shared/ui";
import { BaseFieldProps, useFieldError } from "./useFieldError";

export function TextField<T extends FieldValues>({
  name,
  label,
  hint,
  required,
  className,
  rules,
  disabled,
  type = "text",
  placeholder,
  autoComplete,
  inputMode,
  maxLength,
}: BaseFieldProps<T> & {
  type?: "text" | "email" | "tel" | "url" | "date" | "month" | "number";
  placeholder?: string;
  autoComplete?: string;
  inputMode?: "text" | "email" | "tel" | "numeric" | "url";
  maxLength?: number;
}) {
  const { register } = useFormContext<T>();
  const error = useFieldError(name);
  return (
    <Field label={label} hint={hint} error={error} required={required} className={className}>
      {(props) => (
        <Input
          {...props}
          {...register(name, rules)}
          type={type}
          invalid={Boolean(error)}
          placeholder={placeholder}
          autoComplete={autoComplete}
          inputMode={inputMode}
          maxLength={maxLength}
          disabled={disabled}
        />
      )}
    </Field>
  );
}
