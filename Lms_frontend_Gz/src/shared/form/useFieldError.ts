import type { ReactNode } from "react";
import { get, useFormContext, type FieldValues, type Path, type RegisterOptions } from "react-hook-form";

export interface BaseFieldProps<T extends FieldValues> {
  name: Path<T>;
  label: ReactNode;
  hint?: ReactNode;
  required?: boolean;
  className?: string;
  rules?: RegisterOptions<T, Path<T>>;
  disabled?: boolean;
}

export function useFieldError<T extends FieldValues>(name: Path<T>): string | undefined {
  const {
    formState: { errors },
  } = useFormContext<T>();
  return get(errors, name)?.message as string | undefined;
}
