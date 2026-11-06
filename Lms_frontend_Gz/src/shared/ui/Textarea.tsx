import { forwardRef, type TextareaHTMLAttributes } from "react";

import { cn } from "@/core/lib/cn";
import { controlClass } from "./controlStyles";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean }>(
  function Textarea({ invalid, className, rows = 3, ...props }, ref) {
    return <textarea ref={ref} rows={rows} className={controlClass(invalid, cn("py-2", className))} {...props} />;
  },
);
