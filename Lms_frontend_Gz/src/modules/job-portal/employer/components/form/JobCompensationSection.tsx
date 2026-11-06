import type { JobSectionProps } from "@/modules/job-portal/employer/components/form/JobBasicsSection";
import { Field, Input, Select } from "@/shared/ui";

export function JobCompensationSection({ values: v, set }: JobSectionProps) {
  const isInternship = v.employment_type === "internship";

  const getPeriodUnit = () => {
    if (v.salary_period === "monthly") return `${v.currency}/month`;
    if (v.salary_period === "hourly") return `${v.currency}/hour`;
    return v.currency === "INR" ? "₹ Lakhs/year" : `${v.currency} Thousands/year`;
  };

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Salary Period">
          {(p) => (
            <Select
              {...p}
              value={v.salary_period}
              options={[
                { value: "annual", label: "Annual (Per Year)" },
                { value: "monthly", label: "Monthly (Per Month)" },
                { value: "hourly", label: "Hourly (Per Hour)" },
              ]}
              onChange={(e) => set("salary_period", e.target.value as any)}
            />
          )}
        </Field>

        <Field label="Currency">
          {(p) => (
            <Select
              {...p}
              value={v.currency}
              options={["INR", "USD", "EUR", "GBP"].map((c) => ({ value: c, label: c }))}
              onChange={(e) => set("currency", e.target.value)}
            />
          )}
        </Field>

        {isInternship ? (
          <>
            <Field label={`Stipend per month (${v.currency})`} hint="Leave empty if unpaid internship.">
              {(p) => (
                <Input
                  {...p}
                  type="number"
                  min={0}
                  step="500"
                  placeholder="e.g. 25000"
                  disabled={v.is_negotiable}
                  value={v.stipend_per_month}
                  onChange={(e) => set("stipend_per_month", e.target.value)}
                />
              )}
            </Field>
            <Field label="Duration (months)">
              {(p) => (
                <Input
                  {...p}
                  type="number"
                  min={1}
                  max={36}
                  placeholder="e.g. 6"
                  value={v.duration_months}
                  onChange={(e) => set("duration_months", e.target.value)}
                />
              )}
            </Field>
          </>
        ) : (
          <>
            <Field label={`Minimum Salary (${getPeriodUnit()})`}>
              {(p) => (
                <Input
                  {...p}
                  type="number"
                  min={0}
                  step="0.5"
                  placeholder="e.g. 6.0"
                  disabled={v.is_negotiable}
                  value={v.ctc_min_lakhs}
                  onChange={(e) => set("ctc_min_lakhs", e.target.value)}
                />
              )}
            </Field>
            <Field label={`Maximum Salary (${getPeriodUnit()})`}>
              {(p) => (
                <Input
                  {...p}
                  type="number"
                  min={0}
                  step="0.5"
                  placeholder="e.g. 12.0"
                  disabled={v.is_negotiable}
                  value={v.ctc_max_lakhs}
                  onChange={(e) => set("ctc_max_lakhs", e.target.value)}
                />
              )}
            </Field>
          </>
        )}
      </div>

      <div className="pt-1">
        <label className="flex items-center gap-2 cursor-pointer select-none text-sm text-slate-700">
          <input
            type="checkbox"
            checked={v.is_negotiable}
            onChange={(e) => set("is_negotiable", e.target.checked)}
            className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
          />
          <span className="font-medium">Salary is negotiable / Disclose upon interview</span>
        </label>
      </div>
    </div>
  );
}
