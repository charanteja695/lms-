import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/core/lib/cn";
import { Icon, type IconName } from "./Icon";
import { Spinner } from "./Spinner";

const variants = {
  primary: "bg-brand-700 text-white shadow-brand hover:bg-brand-800 disabled:opacity-50 disabled:shadow-none",
  secondary: "border border-slate-200/90 bg-white text-navy-950 shadow-card hover:border-brand-300 hover:bg-slate-50 hover:text-brand-800 disabled:text-slate-400 disabled:shadow-none",
  danger: "bg-red-600 text-white shadow-sm hover:bg-red-700 disabled:opacity-50",
  ghost: "text-slate-600 hover:bg-slate-100/90 hover:text-slate-900 disabled:text-slate-300",
  link: "text-brand-600 hover:text-brand-700 hover:underline underline-offset-4 px-0 py-0 h-auto",
} as const;

const sizes = {
  sm: "h-9 gap-1.5 rounded-lg px-3 text-sm",
  md: "h-10 gap-2 rounded-xl px-4 text-sm",
  lg: "h-12 gap-2 rounded-xl px-6 text-[15px]",
  icon: "h-10 w-10 rounded-xl justify-center",
} as const;

/** An icon with no text is a square of the same height as its row's other buttons. */
const iconOnly = { sm: "w-9 px-0", md: "w-10 px-0", lg: "w-12 px-0", icon: "" } as const;

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof variants;
  size?: keyof typeof sizes;
  loading?: boolean;
  icon?: IconName;
  fullWidth?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading = false, icon, fullWidth, className, children, disabled, type = "button", ...props },
  ref,
) {
  const onlyIcon = Boolean(icon) && (children === undefined || children === null || children === false);
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      // an icon-only button explains itself on hover with its accessible name
      title={onlyIcon ? (props.title ?? props["aria-label"]) : props.title}
      className={cn(
        "inline-flex shrink-0 cursor-pointer items-center justify-center whitespace-nowrap font-semibold transition-[background-color,border-color,color,box-shadow,transform] duration-150 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:active:scale-100",
        variants[variant],
        sizes[size],
        onlyIcon && iconOnly[size],
        fullWidth && "w-full",
        className,
      )}
      {...props}
    >
      {loading ? <Spinner size={16} /> : icon ? <Icon name={icon} size={16} /> : null}
      {children}
    </button>
  );
});
