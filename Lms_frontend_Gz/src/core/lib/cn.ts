import clsx, { type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Joins class names; a later Tailwind class wins over a conflicting earlier one (so a `className` prop can override a component's base, e.g. `w-28` over `w-full`). */
export function cn(...values: ClassValue[]): string {
  return twMerge(clsx(values));
}
