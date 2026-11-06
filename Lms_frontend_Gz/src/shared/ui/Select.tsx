import { forwardRef, type SelectHTMLAttributes } from "react";

import { cn } from "@/core/lib/cn";
import { controlClass } from "./controlStyles";

export interface Option<T extends string = string> {
  value: T;
  label: string;
}

export const Select = forwardRef<
  HTMLSelectElement,
  SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean; options: readonly Option[]; placeholder?: string }
>(function Select({ invalid, className, options, placeholder, ...props }, ref) {
  return (
    <select ref={ref} className={controlClass(invalid, cn("select-chevron h-11 cursor-pointer truncate pr-10", className))} {...props}>
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
});
