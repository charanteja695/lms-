import { useId, type ReactNode } from "react";

import { cn } from "@/core/lib/cn";

export interface FieldProps {
  label?: ReactNode;
  hint?: ReactNode;
  error?: string;
  required?: boolean;
  className?: string;
  children: (props: { id: string; "aria-invalid": boolean; "aria-describedby"?: string }) => ReactNode;
}

/** Label + control + error with correct accessibility wiring. */
export function Field({ label, hint: _hint, error, required, className, children }: FieldProps) {
  const id = useId();
  const describedBy = error ? `${id}-error` : undefined;
  return (
    <div className={cn("space-y-1.5", className)}>
      {label && (
        // The asterisk sits outside the label so the field's accessible name is exactly the label text.
        <span className="flex items-center gap-0.5">
          <label htmlFor={id} className="block text-sm font-semibold text-slate-800">
            {label}
          </label>
          {required && (
            <span className="text-red-500" aria-hidden="true">
              *
            </span>
          )}
        </span>
      )}
      {children({ id, "aria-invalid": Boolean(error), "aria-describedby": describedBy })}
      {error && (
        <p id={`${id}-error`} role="alert" className="text-xs font-medium text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
