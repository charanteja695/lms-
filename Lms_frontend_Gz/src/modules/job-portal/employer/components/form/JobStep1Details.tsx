import { useState, useId } from "react";
import { Icon } from "@/shared/ui";
import { cn } from "@/core/lib/cn";
import type { EmploymentType, LocationType } from "@/modules/job-portal/common/types";
import type { JobFormValues } from "@/modules/job-portal/employer/form/jobForm";
import { EntityPicker } from "@/shared/ui";
import { useEmployerOptions } from "@/modules/user-management/common/hooks/useEntityOptions";

interface Props {
  values: JobFormValues;
  set: <K extends keyof JobFormValues>(key: K, value: JobFormValues[K]) => void;
  locked: boolean;
  isAdmin: boolean;
  errors?: Record<string, string>;
}

const COMMON_LOCATIONS = [
  "Bengaluru",
  "Hyderabad",
  "Pune",
  "Mumbai",
  "Delhi NCR",
  "Chennai",
  "Remote",
];

export function JobStep1Details({ values: v, set, locked, isAdmin, errors = {} }: Props) {
  const [locInput, setLocInput] = useState("");
  const inputId = useId();

  // Parse locations into array of tags defensively
  const locationList = v.locations
    ? v.locations.split(",").map((s) => s.trim()).filter(Boolean)
    : [];

  const addLocation = (loc: string) => {
    const trimmed = loc.trim().replace(/^,+|,+$/g, "");
    if (!trimmed) return;
    if (!locationList.map((l) => l.toLowerCase()).includes(trimmed.toLowerCase())) {
      const next = [...locationList, trimmed];
      set("locations", next.join(", "));
    }
    setLocInput("");
  };

  const removeLocation = (index: number) => {
    const next = locationList.filter((_, i) => i !== index);
    set("locations", next.join(", "));
  };

  const handleLocKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addLocation(locInput);
    }
  };

  const isInternship = v.employment_type === "internship";

  const getSalaryUnitLabel = () => {
    if (v.salary_period === "monthly") return `per month (${v.currency || "INR"})`;
    if (v.salary_period === "hourly") return `per hour (${v.currency || "INR"})`;
    return (v.currency || "INR") === "INR" ? "LPA (Lakhs/year)" : `k/year (${v.currency || "USD"})`;
  };

  const minVal = parseFloat(v.ctc_min_lakhs || "");
  const maxVal = parseFloat(v.ctc_max_lakhs || "");
  const salaryRangeError =
    !v.is_negotiable &&
    !isNaN(minVal) &&
    !isNaN(maxVal) &&
    minVal > maxVal
      ? "Minimum salary cannot exceed maximum salary"
      : null;

  return (
    <div className="space-y-7">
      {/* 1. Hiring Company (For Admins) */}
      {isAdmin && (
        <div className="space-y-2 scroll-mt-24" id="field-company">
          <label className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1">
            <span>Hiring Company</span>
            <span className="text-rose-500 font-bold">*</span>
          </label>
          <div className="p-3.5 rounded-xl border border-slate-200 bg-slate-50/70 space-y-3">
            <EntityPicker
              label="Select Hiring Company"
              aria-label="Select hiring company"
              required
              value={v.company?.id ?? ""}
              selectedLabel={v.company?.label || undefined}
              useOptions={useEmployerOptions}
              disabled={locked}
              placeholder="Search and select employer organization..."
              hint="Select verified partner employer organization"
              onChange={(id, label) => {
                set("company", id ? { id, label } : null);
              }}
            />
            {v.company && v.company.id && (
              <div className="flex items-center gap-3 pt-1 border-t border-slate-200/80">
                <div className="w-9 h-9 rounded-lg bg-emerald-600 text-white font-bold text-sm flex items-center justify-center shrink-0 shadow-sm">
                  {(v.company.label || "C").charAt(0).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <div className="text-xs font-bold text-slate-900 truncate">{v.company.label}</div>
                  <div className="text-[11px] text-slate-500">Verified LMS Employer Partner</div>
                </div>
              </div>
            )}
          </div>
          {errors.company && <p className="text-xs text-rose-600 font-medium">{errors.company}</p>}
        </div>
      )}

      {/* 2. Job Title & Department */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-1.5 scroll-mt-24" id="field-title">
          <label htmlFor={`${inputId}-title`} className="text-xs font-semibold text-slate-800 flex items-center gap-1">
            <span>Job Title</span>
            <span className="text-rose-500 font-bold">*</span>
          </label>
          <input
            id={`${inputId}-title`}
            type="text"
            value={v.title || ""}
            disabled={locked}
            maxLength={160}
            onChange={(e) => set("title", e.target.value)}
            placeholder="e.g., Senior Full Stack Engineer"
            className={cn(
              "w-full h-11 px-3.5 text-xs text-slate-900 rounded-xl border bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 transition-all",
              errors.title ? "border-rose-400 focus:border-rose-500" : "border-slate-300 focus:border-emerald-600"
            )}
          />
          {errors.title && <p className="text-xs text-rose-600 font-medium">{errors.title}</p>}
        </div>

        <div className="space-y-1.5 scroll-mt-24" id="field-department">
          <label htmlFor={`${inputId}-department`} className="text-xs font-semibold text-slate-800 flex items-center justify-between">
            <span>Department or Industry</span>
            <span className="text-[11px] text-slate-400 font-normal">Optional</span>
          </label>
          <input
            id={`${inputId}-department`}
            type="text"
            value={v.department || ""}
            disabled={locked}
            maxLength={100}
            onChange={(e) => set("department", e.target.value)}
            placeholder="e.g., Engineering, Data Science, Product"
            className="w-full h-11 px-3.5 text-xs text-slate-900 rounded-xl border border-slate-300 bg-white focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 transition-all"
          />
        </div>
      </div>

      {/* 3. Job Type (Segmented Buttons) */}
      <div className="space-y-2 scroll-mt-24" id="field-employment_type">
        <label className="text-xs font-semibold text-slate-800 flex items-center gap-1">
          <span>Job Type</span>
          <span className="text-rose-500 font-bold">*</span>
        </label>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {[
            { value: "full_time", label: "Full-time" },
            { value: "part_time", label: "Part-time" },
            { value: "internship", label: "Internship" },
            { value: "contract", label: "Contract" },
          ].map((type) => {
            const isSelected = (v.employment_type || "full_time") === type.value;
            return (
              <button
                key={type.value}
                type="button"
                disabled={locked}
                onClick={() => set("employment_type", type.value as EmploymentType)}
                className={cn(
                  "h-10 px-3 rounded-xl text-xs font-semibold transition-all border text-center flex items-center justify-center",
                  isSelected
                    ? "bg-emerald-600 text-white border-emerald-600 shadow-sm ring-2 ring-emerald-600/20"
                    : "bg-white text-slate-700 border-slate-300 hover:border-slate-400 hover:bg-slate-50"
                )}
              >
                {type.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* 4. Work Mode (Segmented Buttons) & Remote Eligible */}
      <div className="space-y-3 scroll-mt-24" id="field-location_type">
        <div>
          <label className="text-xs font-semibold text-slate-800 flex items-center gap-1">
            <span>Work Mode</span>
            <span className="text-rose-500 font-bold">*</span>
          </label>
          <div className="grid grid-cols-3 gap-2 mt-2">
            {[
              { value: "onsite", label: "On-site", desc: "Work from office" },
              { value: "hybrid", label: "Hybrid", desc: "Mix of office & home" },
              { value: "remote", label: "Remote", desc: "100% work from anywhere" },
            ].map((mode) => {
              const isSelected = (v.location_type || "onsite") === mode.value;
              return (
                <button
                  key={mode.value}
                  type="button"
                  disabled={locked}
                  onClick={() => set("location_type", mode.value as LocationType)}
                  className={cn(
                    "h-12 px-3 rounded-xl text-left border transition-all flex flex-col justify-center",
                    isSelected
                      ? "bg-emerald-50 border-emerald-600 ring-2 ring-emerald-600/20 text-emerald-950 shadow-sm"
                      : "bg-white border-slate-300 hover:border-slate-400 text-slate-800 hover:bg-slate-50"
                  )}
                >
                  <span className={cn("text-xs font-bold leading-tight", isSelected ? "text-emerald-900" : "text-slate-800")}>
                    {mode.label}
                  </span>
                  <span className="text-[10px] text-slate-500 truncate">{mode.desc}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Remote Eligible Toggle - visible only for Hybrid or Remote */}
        {(v.location_type === "hybrid" || v.location_type === "remote") && (
          <div className="p-3.5 rounded-xl border border-emerald-200/80 bg-emerald-50/40 flex items-center justify-between gap-3">
            <div>
              <span className="text-xs font-bold text-emerald-950 block">Remote Eligible</span>
              <span className="text-[11px] text-slate-600">
                Display prominent "Remote eligible" green badge to students browsing from any city
              </span>
            </div>
            <label className="relative inline-flex items-center cursor-pointer shrink-0">
              <input
                type="checkbox"
                checked={Boolean(v.remote_eligible)}
                disabled={locked}
                onChange={(e) => set("remote_eligible", e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-9 h-5 bg-slate-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-emerald-600"></div>
            </label>
          </div>
        )}
      </div>

      {/* 5. Locations (Multi-Location Tag Input) */}
      <div className="space-y-2 scroll-mt-24" id="field-locations">
        <label htmlFor={`${inputId}-locations`} className="text-xs font-semibold text-slate-800 flex items-center justify-between">
          <span className="flex items-center gap-1">
            <span>Locations</span>
            {v.location_type !== "remote" && <span className="text-rose-500 font-bold">*</span>}
          </span>
          <span className="text-[11px] text-slate-400 font-normal">
            {v.location_type === "remote" ? "Optional for 100% remote" : "Type city and press Enter"}
          </span>
        </label>

        {/* Input & Chips Box */}
        <div
          className={cn(
            "p-2 rounded-xl border bg-white min-h-[48px] flex flex-wrap items-center gap-1.5 focus-within:ring-2 focus-within:ring-emerald-500/20 transition-all",
            errors.locations ? "border-rose-400 focus-within:border-rose-500" : "border-slate-300 focus-within:border-emerald-600"
          )}
        >
          {locationList.map((loc, idx) => (
            <span
              key={idx}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200"
            >
              <span>{loc}</span>
              {!locked && (
                <button
                  type="button"
                  onClick={() => removeLocation(idx)}
                  className="hover:text-emerald-950 p-0.5 rounded text-emerald-600"
                  aria-label={`Remove ${loc}`}
                >
                  <Icon name="x" className="h-3 w-3" />
                </button>
              )}
            </span>
          ))}

          <input
            id={`${inputId}-locations`}
            type="text"
            value={locInput}
            disabled={locked}
            onChange={(e) => setLocInput(e.target.value)}
            onKeyDown={handleLocKeyDown}
            onBlur={() => addLocation(locInput)}
            placeholder={locationList.length === 0 ? "e.g., Bengaluru, Hyderabad (press Enter or comma)" : "Add more..."}
            className="flex-1 min-w-[140px] text-xs text-slate-900 bg-transparent px-2 py-1 focus:outline-none placeholder:text-slate-400"
          />
        </div>

        {/* Suggestions chips */}
        <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
          <span className="text-[11px] text-slate-400">Suggestions:</span>
          {COMMON_LOCATIONS.map((city) => {
            const alreadyAdded = locationList.map((l) => l.toLowerCase()).includes(city.toLowerCase());
            return (
              <button
                key={city}
                type="button"
                disabled={locked || alreadyAdded}
                onClick={() => addLocation(city)}
                className={cn(
                  "text-[11px] px-2 py-0.5 rounded-md border transition-all",
                  alreadyAdded
                    ? "bg-slate-100 text-slate-400 border-slate-200 cursor-default"
                    : "bg-white text-slate-600 border-slate-300 hover:border-emerald-500 hover:text-emerald-700 hover:bg-emerald-50/50"
                )}
              >
                + {city}
              </button>
            );
          })}
        </div>
        {errors.locations && <p className="text-xs text-rose-600 font-medium">{errors.locations}</p>}
      </div>

      {/* 6. Number of Openings & Application Deadline */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-1.5 scroll-mt-24" id="field-openings">
          <label htmlFor={`${inputId}-openings`} className="text-xs font-semibold text-slate-800 flex items-center gap-1">
            <span>Number of Openings</span>
            <span className="text-rose-500 font-bold">*</span>
          </label>
          <input
            id={`${inputId}-openings`}
            type="number"
            min={1}
            max={10000}
            value={v.openings || "1"}
            disabled={locked}
            onChange={(e) => set("openings", e.target.value)}
            placeholder="1"
            className="w-full h-11 px-3.5 text-xs text-slate-900 rounded-xl border border-slate-300 bg-white focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 transition-all"
          />
        </div>

        <div className="space-y-1.5 scroll-mt-24" id="field-deadline">
          <label htmlFor={`${inputId}-deadline`} className="text-xs font-semibold text-slate-800 flex items-center gap-1">
            <span>Application Deadline</span>
            <span className="text-rose-500 font-bold">*</span>
          </label>
          <input
            id={`${inputId}-deadline`}
            type="date"
            value={v.deadline || ""}
            disabled={locked}
            onChange={(e) => set("deadline", e.target.value)}
            className={cn(
              "w-full h-11 px-3.5 text-xs text-slate-900 rounded-xl border bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 transition-all",
              errors.deadline ? "border-rose-400 focus:border-rose-500" : "border-slate-300 focus:border-emerald-600"
            )}
          />
          {errors.deadline && <p className="text-xs text-rose-600 font-medium">{errors.deadline}</p>}
        </div>
      </div>

      {/* 7. Salary & Compensation */}
      <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-4 scroll-mt-24" id="field-salary">
        <div className="flex items-center justify-between border-b border-slate-200 pb-2.5">
          <div>
            <h4 className="text-xs font-bold text-slate-900">Salary & Compensation</h4>
            <p className="text-[11px] text-slate-500">Specify compensation package or stipend for candidates</p>
          </div>
          {/* Currency Select */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-slate-500 font-medium">Currency:</span>
            <select
              value={v.currency || "INR"}
              disabled={locked}
              onChange={(e) => set("currency", e.target.value)}
              className="text-xs font-bold border border-slate-300 rounded-lg bg-white px-2.5 py-1 text-slate-900 focus:outline-none focus:ring-1 focus:ring-emerald-500 shadow-sm"
            >
              <option value="INR">INR (₹)</option>
              <option value="USD">USD ($)</option>
              <option value="EUR">EUR (€)</option>
              <option value="GBP">GBP (£)</option>
            </select>
          </div>
        </div>

        {/* Period Selector */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-700">Salary Period</label>
          <div className="grid grid-cols-3 gap-2">
            {[
              { value: "annual", label: "Annual (CTC)" },
              { value: "monthly", label: "Monthly" },
              { value: "hourly", label: "Hourly" },
            ].map((p) => (
              <button
                key={p.value}
                type="button"
                disabled={locked}
                onClick={() => set("salary_period", p.value as any)}
                className={cn(
                  "h-9 px-2 rounded-lg text-xs font-semibold border transition-all text-center",
                  (v.salary_period || "annual") === p.value
                    ? "bg-white text-emerald-800 border-emerald-600 shadow-sm font-bold ring-1 ring-emerald-600"
                    : "bg-slate-100 text-slate-600 border-transparent hover:bg-white"
                )}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        {/* Salary range inputs */}
        {isInternship ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
            <div className="space-y-1">
              <label htmlFor={`${inputId}-stipend`} className="text-xs font-semibold text-slate-700">
                Stipend ({v.currency || "INR"}/month)
              </label>
              <input
                id={`${inputId}-stipend`}
                type="number"
                min={0}
                step="500"
                value={v.stipend_per_month || ""}
                disabled={locked || v.is_negotiable}
                onChange={(e) => set("stipend_per_month", e.target.value)}
                placeholder="e.g., 25000"
                className="w-full h-10 px-3 text-xs text-slate-900 rounded-lg border border-slate-300 bg-white focus:outline-none focus:border-emerald-600"
              />
            </div>
            <div className="space-y-1">
              <label htmlFor={`${inputId}-duration`} className="text-xs font-semibold text-slate-700">
                Duration (months)
              </label>
              <input
                id={`${inputId}-duration`}
                type="number"
                min={1}
                max={36}
                value={v.duration_months || ""}
                disabled={locked}
                onChange={(e) => set("duration_months", e.target.value)}
                placeholder="e.g., 6"
                className="w-full h-10 px-3 text-xs text-slate-900 rounded-lg border border-slate-300 bg-white focus:outline-none focus:border-emerald-600"
              />
            </div>
          </div>
        ) : (
          <div className="space-y-1.5 pt-1">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label htmlFor={`${inputId}-min-salary`} className="text-xs font-semibold text-slate-700">
                  Minimum Salary ({getSalaryUnitLabel()})
                </label>
                <input
                  id={`${inputId}-min-salary`}
                  type="number"
                  min={0}
                  step="0.5"
                  value={v.ctc_min_lakhs || ""}
                  disabled={locked || v.is_negotiable}
                  onChange={(e) => set("ctc_min_lakhs", e.target.value)}
                  placeholder="e.g., 6.0"
                  className={cn(
                    "w-full h-10 px-3 text-xs text-slate-900 rounded-lg border bg-white focus:outline-none",
                    salaryRangeError ? "border-rose-400 focus:border-rose-500" : "border-slate-300 focus:border-emerald-600"
                  )}
                />
              </div>

              <div className="space-y-1">
                <label htmlFor={`${inputId}-max-salary`} className="text-xs font-semibold text-slate-700">
                  Maximum Salary ({getSalaryUnitLabel()})
                </label>
                <input
                  id={`${inputId}-max-salary`}
                  type="number"
                  min={0}
                  step="0.5"
                  value={v.ctc_max_lakhs || ""}
                  disabled={locked || v.is_negotiable}
                  onChange={(e) => set("ctc_max_lakhs", e.target.value)}
                  placeholder="e.g., 12.0"
                  className={cn(
                    "w-full h-10 px-3 text-xs text-slate-900 rounded-lg border bg-white focus:outline-none",
                    salaryRangeError ? "border-rose-400 focus:border-rose-500" : "border-slate-300 focus:border-emerald-600"
                  )}
                />
              </div>
            </div>
            {salaryRangeError && (
              <p className="text-xs text-rose-600 font-medium pt-0.5">{salaryRangeError}</p>
            )}
          </div>
        )}

        {/* Toggles: Negotiable & Hide salary */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-slate-200">
          <label className="flex items-center gap-2.5 text-xs text-slate-700 cursor-pointer">
            <input
              type="checkbox"
              checked={Boolean(v.is_negotiable)}
              disabled={locked}
              onChange={(e) => set("is_negotiable", e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
            />
            <span className="font-medium">Salary is negotiable based on performance</span>
          </label>

          <label className="flex items-center gap-2.5 text-xs text-slate-700 cursor-pointer">
            <input
              type="checkbox"
              checked={Boolean((v as any).hide_salary)}
              disabled={locked}
              onChange={(e) => set("hide_salary" as any, e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
            />
            <span className="font-medium">Hide salary figures from students</span>
          </label>
        </div>
      </div>
    </div>
  );
}
