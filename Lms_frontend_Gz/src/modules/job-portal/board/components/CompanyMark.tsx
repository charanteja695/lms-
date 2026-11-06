import { cn } from "@/core/lib/cn";

const TONES = ["bg-navy-900", "bg-brand-700", "bg-accent-700", "bg-navy-700", "bg-brand-800"];

/** A company's initial on a logo-coloured tile (picked from the name, so it's stable); companies have no uploaded logo yet. */
export function CompanyMark({ name, size = "md" }: { name: string | null; size?: "md" | "lg" }) {
  const label = (name ?? "?").trim();
  const tone = TONES[[...label].reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % TONES.length];
  return (
    <span aria-hidden="true" className={cn("flex shrink-0 items-center justify-center rounded-xl font-extrabold text-white", tone, size === "lg" ? "h-14 w-14 text-xl" : "h-11 w-11 text-base")}>
      {label.charAt(0).toUpperCase()}
    </span>
  );
}
