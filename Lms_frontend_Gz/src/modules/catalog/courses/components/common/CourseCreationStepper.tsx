import { useNavigate } from "react-router-dom";
import { Icon } from "@/shared/ui";
import { cn } from "@/core/lib/cn";

export type StepStatus = "done" | "current" | "pending";

export interface StepperStepItem {
  id: number;
  label: string;
  sublabel?: string;
  status: StepStatus;
  path?: string;
}

interface CourseCreationStepperProps {
  courseId?: string;
  activeStepId: number;
  steps: StepperStepItem[];
  className?: string;
  onStepClick?: (step: StepperStepItem) => void;
}

export function CourseCreationStepper({
  courseId,
  activeStepId,
  steps,
  className,
  onStepClick,
}: CourseCreationStepperProps) {
  const navigate = useNavigate();

  const handleStepClick = (step: StepperStepItem) => {
    if (onStepClick) {
      onStepClick(step);
      return;
    }
    if (step.path) {
      navigate(step.path);
    }
  };

  return (
    <div className={cn("rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs", className)}>
      <div className="flex items-center justify-between mb-3 px-1">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#00663C]" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">Course Creation Flow</h3>
        </div>
        <span className="text-xs text-slate-500 font-semibold">
          Step {activeStepId} of {steps.length}
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-5 gap-2 relative">
        {steps.map((step) => {
          const isDone = step.status === "done";
          const isCurrent = step.id === activeStepId;
          const isClickable = Boolean(step.path || onStepClick);

          return (
            <button
              key={step.id}
              type="button"
              disabled={!isClickable && !courseId}
              onClick={() => handleStepClick(step)}
              className={cn(
                "flex flex-col text-left p-2.5 rounded-xl transition-all border text-xs cursor-pointer",
                isCurrent
                  ? "bg-emerald-50/80 border-[#00663C] ring-2 ring-[#00663C]/10 shadow-2xs"
                  : isDone
                  ? "bg-slate-50/70 border-slate-200 hover:bg-slate-100/70"
                  : "bg-white border-dashed border-slate-200 text-slate-400 hover:border-slate-300",
                (!isClickable && !courseId) && "cursor-default opacity-60"
              )}
            >
              <div className="flex items-center gap-2 mb-1">
                <div
                  className={cn(
                    "w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold shrink-0 transition-colors",
                    isDone
                      ? "bg-[#00663C] text-white"
                      : isCurrent
                      ? "bg-white border-2 border-[#00663C] text-[#00663C]"
                      : "bg-slate-100 text-slate-400 border border-slate-200"
                  )}
                >
                  {isDone ? (
                    <Icon name="check" size={13} className="text-white" />
                  ) : (
                    step.id
                  )}
                </div>
                <span
                  className={cn(
                    "font-bold truncate text-xs",
                    isCurrent
                      ? "text-[#00663C]"
                      : isDone
                      ? "text-slate-800"
                      : "text-slate-500"
                  )}
                >
                  {step.label}
                </span>
              </div>
              <p className="text-[11px] pl-8 text-slate-400 font-medium truncate">
                {step.sublabel || (isDone ? "Done" : isCurrent ? "In progress" : "Not started")}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
