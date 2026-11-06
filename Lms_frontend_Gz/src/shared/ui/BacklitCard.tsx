import { type ReactNode } from "react";
import { motion, type HTMLMotionProps } from "motion/react";
import { cn } from "@/core/lib/cn";

export type BacklightTone = "brand" | "navy" | "accent" | "logo";

const GLOW_TONES: Record<BacklightTone, string> = {
  brand: "from-brand-500/25 via-brand-600/15 to-brand-400/10",
  navy: "from-navy-600/25 via-navy-800/15 to-navy-500/10",
  accent: "from-accent-500/25 via-accent-600/15 to-accent-400/10",
  logo: "from-brand-500/25 via-navy-700/20 to-accent-500/20",
};

export interface BacklitCardProps extends HTMLMotionProps<"div"> {
  children: ReactNode;
  backlightTone?: BacklightTone;
  interactive?: boolean;
  className?: string;
  innerClassName?: string;
}

/**
 * Backlit UI / Kokonut UI Card:
 * Features a glowing ambient radiant backlight inspired by our GenZ logo colors (Green, Navy, Accent Orange).
 * Provides a modern Soft UI card surface that softly illuminates on rest and expands its glow on hover.
 */
export function BacklitCard({
  children,
  backlightTone = "logo",
  interactive = true,
  className,
  innerClassName,
  ...props
}: BacklitCardProps) {
  return (
    <motion.div
      whileHover={interactive ? { y: -3, transition: { duration: 0.2, ease: "easeOut" } } : undefined}
      whileTap={interactive ? { scale: 0.99 } : undefined}
      className={cn("group relative", className)}
      {...props}
    >
      {/* Ambient Backlight Glow (Kokonut UI / Backlit pattern) */}
      <div
        className={cn(
          "absolute -inset-1 rounded-3xl bg-gradient-to-r opacity-30 blur-lg transition-all duration-500",
          interactive && "group-hover:-inset-1.5 group-hover:opacity-75 group-hover:blur-xl",
          GLOW_TONES[backlightTone],
        )}
        aria-hidden="true"
      />

      {/* Surface Card Container */}
      <div
        className={cn(
          "relative h-full overflow-hidden rounded-2xl border border-slate-200/90 bg-white p-5 shadow-card transition-all duration-200",
          interactive && "group-hover:border-brand-300 group-hover:shadow-lift",
          innerClassName,
        )}
      >
        {children}
      </div>
    </motion.div>
  );
}
