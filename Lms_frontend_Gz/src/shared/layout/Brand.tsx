import { env } from "@/core/config/env";
import { cn } from "@/core/lib/cn";
import { Icon } from "@/shared/ui";
import { LogoMark } from "./LogoMark";

export function Brand({
  collapsed = false,
  onCloseMobile,
}: {
  collapsed?: boolean;
  onCloseMobile?: () => void;
}) {
  return (
    <div
      className={cn(
        "flex h-16 items-center border-b border-slate-100 transition-all duration-200",
        collapsed ? "justify-center px-2" : "justify-between px-4 sm:px-5",
      )}
    >
      <div className="flex items-center gap-3 min-w-0">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white">
          <LogoMark className="h-8 w-8" />
        </span>
        {!collapsed && (
          <div className="min-w-0 leading-tight">
            <p className="truncate text-[15px] font-bold text-navy-950 tracking-tight">{env.appName}</p>
            {env.organizationName && (
              <p className="truncate text-[11px] font-medium text-slate-500">{env.organizationName}</p>
            )}
          </div>
        )}
      </div>

      {onCloseMobile && (
        <button
          type="button"
          onClick={onCloseMobile}
          className="flex h-9 w-9 items-center justify-center rounded-xl text-slate-500 transition-colors hover:bg-slate-100 hover:text-navy-950 cursor-pointer lg:hidden"
          aria-label="Close navigation"
        >
          <Icon name="x" size={18} />
        </button>
      )}
    </div>
  );
}
