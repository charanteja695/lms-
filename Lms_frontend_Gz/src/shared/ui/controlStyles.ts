import { cn } from "@/core/lib/cn";

// Soft UI controls: a quiet border that firms up on hover, and a soft brand halo (not a hard outline) when focused
const controlBase =
  "block w-full rounded-xl border bg-white px-3.5 text-sm text-slate-900 shadow-[0_1px_2px_rgb(16_24_40/0.04)] placeholder:text-slate-400 " +
  "transition-[border-color,box-shadow] duration-150 hover:border-slate-300 " +
  "focus:border-brand-500 focus:outline-none focus:ring-4 focus:ring-brand-500/15 disabled:bg-slate-50 disabled:text-slate-500";

export function controlClass(invalid: boolean | undefined, className?: string) {
  return cn(controlBase, invalid ? "border-red-400 focus:border-red-500 focus:ring-red-500/15" : "border-slate-200", className);
}
