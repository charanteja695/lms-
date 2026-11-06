import { cn } from "@/core/lib/cn";
import { Icon } from "@/shared/ui";

export interface SetupStep {
  id: number;
  label: string;
  sublabel: string;
  status: "done" | "current" | "pending";
  path?: string;
  onClick?: () => void;
}

interface SetupProgressProps {
  steps: SetupStep[];
  onStepClick?: (step: SetupStep) => void;
  className?: string;
}

export function SetupProgress({ steps, onStepClick, className }: SetupProgressProps) {
  const doneCount = steps.filter((s) => s.status === "done").length;

  return (
    <div className={cn("rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs", className)}>
      <div className="flex items-center justify-between gap-3 mb-5">
        <div>
          <h3 className="text-sm font-bold text-[#0A1530]">Setup progress</h3>
          <p className="text-xs text-slate-400 font-medium mt-0.5">
            Click any step to configure it. All 5 steps must be complete before publishing.
          </p>
        </div>
        <span
          className={cn(
            "text-xs font-bold px-2.5 py-1 rounded-full",
            doneCount === steps.length
              ? "bg-[#E7F3EC] text-[#00663C]"
              : "bg-slate-100 text-slate-600"
          )}
        >
          {doneCount} of {steps.length} done
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 sm:gap-2">
        {steps.map((step) => {
          const isDone = step.status === "done";
          const isCurrent = step.status === "current";
          const isClickable = Boolean(step.onClick || onStepClick);

          return (
            <button
              key={step.id}
              type="button"
              onClick={() => {
                if (step.onClick) step.onClick();
                else if (onStepClick) onStepClick(step);
              }}
              className={cn(
                "relative flex flex-col gap-1.5 p-3 rounded-xl transition-all text-left border cursor-pointer",
                isCurrent
                  ? "bg-emerald-50/50 border-[#00663C]/40 ring-2 ring-[#00663C]/10"
                  : isDone
                  ? "bg-slate-50/70 border-slate-200 hover:bg-slate-100/70"
                  : "bg-white border-dashed border-slate-200 hover:border-slate-300",
                !isClickable && "cursor-default"
              )}
            >
              <div className="flex items-center gap-2">
                <div
                  className={cn(
                    "w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all shrink-0",
                    isDone
                      ? "bg-[#00663C] text-white"
                      : isCurrent
                      ? "border-2 border-[#00663C] text-[#00663C] bg-white ring-4 ring-[#E7F3EC]"
                      : "border-2 border-slate-300 text-slate-400 bg-white"
                  )}
                >
                  {isDone ? (
                    <Icon name="check" size={14} className="text-white" />
                  ) : (
                    step.id
                  )}
                </div>
                <b className="text-xs font-bold text-[#0A1530] truncate">{step.label}</b>
              </div>
              <p className="text-[11px] text-slate-500 pl-9 font-medium truncate">{step.sublabel}</p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
