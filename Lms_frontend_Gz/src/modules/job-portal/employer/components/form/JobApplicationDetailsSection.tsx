import type { JobSectionProps } from "@/modules/job-portal/employer/components/form/JobBasicsSection";
import { Field, Input, Select } from "@/shared/ui";

export function JobApplicationDetailsSection({ values: v, set }: JobSectionProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Application Deadline" required hint="Last date for students to submit applications.">
        {(p) => <Input {...p} type="date" value={v.deadline} onChange={(e) => set("deadline", e.target.value)} />}
      </Field>

      <Field label="Number of Vacancies / Openings" required hint="Total positions available.">
        {(p) => <Input {...p} type="number" min={1} max={10000} placeholder="1" value={v.openings} onChange={(e) => set("openings", e.target.value)} />}
      </Field>

      <Field label="Application Option" required>
        {(p) => (
          <Select
            {...p}
            value={v.application_type}
            options={[
              { value: "internal", label: "Internal Application (Apply directly through ExamLMS)" },
              { value: "external", label: "External Application URL (Redirect candidate to external link)" },
            ]}
            onChange={(e) => set("application_type", e.target.value as any)}
          />
        )}
      </Field>

      <Field label="Contact Email" hint="HR or recruiter contact email for student queries.">
        {(p) => <Input {...p} type="email" placeholder="hr@company.com" value={v.contact_email} onChange={(e) => set("contact_email", e.target.value)} />}
      </Field>

      {v.application_type === "external" && (
        <Field label="External Job Application URL" required hint="Web link where candidates will complete their application." className="sm:col-span-2">
          {(p) => <Input {...p} type="url" placeholder="https://careers.company.com/apply/..." value={v.application_url} onChange={(e) => set("application_url", e.target.value)} />}
        </Field>
      )}
    </div>
  );
}
