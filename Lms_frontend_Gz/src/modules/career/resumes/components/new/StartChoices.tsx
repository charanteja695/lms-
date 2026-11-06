import { cn } from "@/core/lib/cn";
import type { ResumeOptions } from "@/modules/career/resumes/types";
import { FileDropzone, Input } from "@/shared/ui";

export interface StartState {
  start: string;
  level: string;
  role: string;
  file: File | null;
}

/** The three choices of a new resume: where to start, experience level, target role. */
export function StartChoices({
  options,
  value,
  onChange,
}: {
  options: ResumeOptions;
  value: StartState;
  onChange: (next: Partial<StartState>) => void;
}) {
  const start = options.start_options.find((o) => o.key === value.start);
  const level = options.experience_levels.find((l) => l.key === value.level);

  return (
    <div className="space-y-5">
      {/* 1. Start from */}
      <fieldset className="space-y-2.5">
        <legend className="text-sm font-bold text-navy-950">1 · Start from</legend>
        <div role="radiogroup" className="grid gap-2 sm:grid-cols-2">
          {options.start_options.map((option) => {
            const on = option.key === value.start;
            return (
              <button
                key={option.key}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => onChange({ start: option.key, file: null })}
                className={cn(
                  "flex min-h-[58px] flex-col items-start justify-center rounded-xl p-3 text-left transition-all",
                  on
                    ? "bg-brand-50/70 border-2 border-brand-600 shadow-2xs"
                    : "bg-white border border-slate-200 hover:border-slate-300 hover:bg-slate-50/50",
                )}
              >
                <span className="text-sm font-bold text-navy-950">{option.label}</span>
                <span className="text-xs text-slate-500 line-clamp-1">{option.description}</span>
              </button>
            );
          })}
        </div>

        {start && start.accepts.length > 0 && (
          <div className="pt-1">
            <FileDropzone
              file={value.file}
              onFileChange={(file) => onChange({ file })}
              accept={start.accepts.join(",")}
              maxBytes={options.max_import_bytes}
              hint={`${start.accepts.join(", ").toUpperCase()} · up to ${Math.round(
                options.max_import_bytes / 1024 / 1024,
              )} MB. Read safely without overwriting existing data.`}
            />
          </div>
        )}
      </fieldset>

      {/* 2. Experience */}
      <fieldset>
        <legend className="mb-2 text-sm font-bold text-navy-950">2 · Experience</legend>
        <div role="radiogroup" className="flex flex-wrap gap-1 rounded-xl bg-slate-100/90 p-1 border border-slate-200/80">
          {options.experience_levels.map((option) => (
            <button
              key={option.key}
              type="button"
              role="radio"
              aria-checked={option.key === value.level}
              onClick={() => onChange({ level: option.key })}
              className={cn(
                "min-h-[38px] flex-1 rounded-lg px-3 text-xs sm:text-sm font-semibold transition-all",
                option.key === value.level
                  ? "bg-white text-navy-950 shadow-sm border border-slate-200/60 font-bold"
                  : "text-slate-600 hover:text-navy-950",
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
        {level && <p className="mt-1.5 text-xs text-slate-500">{level.note}</p>}
      </fieldset>

      {/* 3. Role you want */}
      <fieldset>
        <label htmlFor="resume-role" className="mb-2 block text-sm font-bold text-navy-950">
          3 · Role you want
        </label>
        <Input
          id="resume-role"
          value={value.role}
          maxLength={120}
          placeholder="Any role — type it or pick one below"
          onChange={(e) => onChange({ role: e.target.value })}
        />
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {options.role_suggestions.map((role) => (
            <button
              key={role}
              type="button"
              aria-pressed={role === value.role}
              onClick={() => onChange({ role })}
              className={cn(
                "min-h-[32px] rounded-full px-3 text-xs font-semibold transition-colors",
                role === value.role
                  ? "bg-brand-50 text-brand-800 border border-brand-500 font-bold"
                  : "bg-white text-slate-600 border border-slate-200 hover:border-slate-300 hover:text-navy-950",
              )}
            >
              {role}
            </button>
          ))}
        </div>
      </fieldset>
    </div>
  );
}
