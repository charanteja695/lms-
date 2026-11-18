import { cn } from "@/core/lib/cn";
import { Icon } from "@/shared/ui";
import { LogoMark } from "./LogoMark";

export function Brand({
  collapsed = false,
  onCloseMobile,
  dark = false,
}: {
  collapsed?: boolean;
  onCloseMobile?: () => void;
  dark?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex h-[68px] items-center transition-all duration-200",
        dark ? "border-b border-slate-800/80" : "border-b border-slate-100",
        collapsed ? "justify-center px-2" : "justify-between px-4 sm:px-5",
      )}
    >
      <div className="flex items-center gap-3 min-w-0">
        <LogoMark className="h-9 w-9" />
        {!collapsed && (
          <div className="min-w-0 leading-tight">
            <p className={cn("truncate text-[16px] font-bold tracking-tight", dark ? "text-white" : "text-navy-950")}>
              ExamLMS
            </p>
            <p className={cn("truncate text-[11px] font-medium tracking-tight", dark ? "text-slate-400" : "text-slate-500")}>
              Learn • Practice • Excel
            </p>
          </div>
        )}
      </div>

      {onCloseMobile && (
        <button
          type="button"
          onClick={onCloseMobile}
          className={cn(
            "flex h-9 w-9 items-center justify-center rounded-xl transition-colors cursor-pointer lg:hidden",
            dark ? "text-slate-400 hover:bg-slate-800 hover:text-white" : "text-slate-500 hover:bg-slate-100 hover:text-navy-950",
          )}
          aria-label="Close navigation"
        >
          <Icon name="x" size={18} />
        </button>
      )}
    </div>
  );
}
