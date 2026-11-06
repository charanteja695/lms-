import type { ReactNode } from "react";

import { cn } from "@/core/lib/cn";
import { Icon, type IconName } from "./Icon";

const alertTones = {
  info: { box: "border-navy-200 bg-navy-50 text-navy-900", icon: "info" },
  success: { box: "border-brand-200 bg-brand-50 text-brand-800", icon: "check" },
  warning: { box: "border-amber-200 bg-amber-50 text-amber-800", icon: "alert" },
  error: { box: "border-red-200 bg-red-50 text-red-800", icon: "alert" },
  danger: { box: "border-red-200 bg-red-50 text-red-800", icon: "alert" },
} as const satisfies Record<string, { box: string; icon: IconName }>;

export function Alert({ tone = "info", title, children, className }: {
  tone?: keyof typeof alertTones | "danger";
  title?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  const style = alertTones[tone as keyof typeof alertTones] ?? alertTones.error;
  return (
    <div role={tone === "error" || tone === "danger" ? "alert" : "status"} className={cn("flex gap-3 rounded-xl border px-4 py-3.5 text-sm", style.box, className)}>
      <Icon name={style.icon} size={18} className="mt-0.5 shrink-0" />
      <div className="space-y-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div>{children}</div>}
      </div>
    </div>
  );
}
