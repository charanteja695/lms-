import logo from "@/assets/logo-mark.png";
import { env } from "@/core/config/env";
import { cn } from "@/core/lib/cn";

/** The GenZ Technologies logo (src/assets/Gen_z-logo.png, resized). One place, so a new logo is a one-file change. */
export function LogoMark({ className }: { className?: string }) {
  return <img src={logo} alt={`${env.appName} logo`} className={cn("h-9 w-9 shrink-0 object-contain", className)} />;
}
