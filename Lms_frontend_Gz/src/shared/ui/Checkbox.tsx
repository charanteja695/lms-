import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from "react";

import { cn } from "@/core/lib/cn";

export const Checkbox = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { label: ReactNode; description?: ReactNode }>(
  function Checkbox({ label, description, className, ...props }, ref) {
    const id = useId();
    return (
      <div className={cn("flex items-start gap-3", className)}>
        <input
          ref={ref}
          id={id}
          type="checkbox"
          className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
          {...props}
        />
        <label htmlFor={id} className="text-sm">
          <span className="font-medium text-slate-700">{label}</span>
          {typeof description !== "string" && description && <span className="block text-slate-500">{description}</span>}
        </label>
      </div>
    );
  },
);
