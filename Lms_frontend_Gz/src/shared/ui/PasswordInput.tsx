import { forwardRef, useState, type InputHTMLAttributes } from "react";

import { cn } from "@/core/lib/cn";
import { controlClass } from "./controlStyles";
import { Icon } from "./Icon";

export const PasswordInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }>(
  function PasswordInput({ invalid, className, ...props }, ref) {
    const [visible, setVisible] = useState(false);
    return (
      <div className="relative">
        <input ref={ref} type={visible ? "text" : "password"} className={controlClass(invalid, cn("h-11 pr-10", className))} {...props} />
        <button
          type="button"
          onClick={() => setVisible((value) => !value)}
          className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-slate-400 hover:text-slate-600"
          aria-label={visible ? "Hide password" : "Show password"}
        >
          <Icon name={visible ? "eyeOff" : "eye"} size={16} />
        </button>
      </div>
    );
  },
);
