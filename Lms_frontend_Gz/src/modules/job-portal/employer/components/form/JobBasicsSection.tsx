import { toOptions } from "@/core/lib/options";
import { EMPLOYMENT_LABELS, LOCATION_TYPE_LABELS } from "@/modules/job-portal/common/labels";
import type { EmploymentType, LocationType } from "@/modules/job-portal/common/types";
import type { JobFormValues } from "@/modules/job-portal/employer/form/jobForm";
import { Field, Input, Select } from "@/shared/ui";

type Props = { values: JobFormValues; set: <K extends keyof JobFormValues>(key: K, value: JobFormValues[K]) => void; locked: boolean };

export function JobBasicsSection({ values: v, set }: Props) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Job Title" required className="sm:col-span-2">
        {(p) => <Input {...p} placeholder="e.g. Senior Frontend Developer" maxLength={160} value={v.title} onChange={(e) => set("title", e.target.value)} />}
      </Field>

      <Field label="Department or Industry" hint="e.g. Information Technology, Engineering, Marketing" className="sm:col-span-2">
        {(p) => <Input {...p} placeholder="e.g. Software Engineering" value={v.department} onChange={(e) => set("department", e.target.value)} />}
      </Field>

      <Field label="Job Type" required>
        {(p) => <Select {...p} value={v.employment_type} options={toOptions(EMPLOYMENT_LABELS)} onChange={(e) => set("employment_type", e.target.value as EmploymentType)} />}
      </Field>

      <Field label="Work Mode" required>
        {(p) => <Select {...p} value={v.location_type} options={toOptions(LOCATION_TYPE_LABELS)} onChange={(e) => set("location_type", e.target.value as LocationType)} />}
      </Field>

      <Field
        label={v.location_type === "remote" ? "Job Location (Optional for Remote)" : "Job Location"}
        required={v.location_type !== "remote"}
        hint="Comma-separated cities or regions (e.g. Bangalore, Hyderabad, Mumbai)."
        className="sm:col-span-2"
      >
        {(p) => <Input {...p} placeholder="e.g. Bangalore, Hyderabad" value={v.locations} onChange={(e) => set("locations", e.target.value)} />}
      </Field>
    </div>
  );
}

export type JobSectionProps = Props;
