import { forwardRef, type InputHTMLAttributes } from "react";

import { cn } from "@/core/lib/cn";
import { controlClass } from "./controlStyles";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }>(function Input(
  { invalid, className, ...props },
  ref,
) {
  return <input ref={ref} className={controlClass(invalid, cn("h-11", className))} {...props} />;
});
