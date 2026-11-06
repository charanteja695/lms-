import { useFormContext, type FieldValues } from "react-hook-form";

import { Checkbox } from "@/shared/ui";
import { BaseFieldProps } from "./useFieldError";

export function CheckboxField<T extends FieldValues>({ name, label, hint, className }: BaseFieldProps<T>) {
  const { register } = useFormContext<T>();
  return <Checkbox {...register(name)} label={label} description={hint} className={className} />;
}
