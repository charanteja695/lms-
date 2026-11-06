import { useHiringTestOptions, useScreeningPlanOptions } from "@/modules/job-portal/employer/api/stagePickersApi";
import type { JobSectionProps } from "@/modules/job-portal/employer/components/form/JobBasicsSection";
import { Alert, Checkbox, EntityPicker, Field, Input } from "@/shared/ui";

/** The stages after shortlisting. A stage that is on can't be skipped, one that is off can't be entered; locked once people apply. */
export function JobPipelineSection({ values: v, set, locked }: JobSectionProps) {
  return (
    <div className="space-y-4">
      {locked && <Alert tone="info">The pipeline is locked once candidates have applied.</Alert>}
      <EntityPicker
        label="Assessment (your published hiring test)"
        value={v.assessment?.id ?? ""}
        selectedLabel={v.assessment?.label}
        disabled={locked}
        useOptions={useHiringTestOptions}
        placeholder="No assessment"
        onChange={(id, label) => set("assessment", id ? { id, label } : null)}
      />
      {v.assessment && (
        <Field label="Pass mark (%)" hint="Empty = the test's own pass mark.">
          {(p) => <Input {...p} type="number" min={0} max={100} className="w-32" disabled={locked} value={v.assessment_min_percent} onChange={(e) => set("assessment_min_percent", e.target.value)} />}
        </Field>
      )}
      <EntityPicker
        label="AI interview (your published screening plan)"
        value={v.ai_interview?.id ?? ""}
        selectedLabel={v.ai_interview?.label}
        disabled={locked}
        useOptions={useScreeningPlanOptions}
        placeholder="No AI interview"
        onChange={(id, label) => set("ai_interview", id ? { id, label } : null)}
      />
      <Checkbox label="HR interview" description="A person interviews shortlisted candidates before an offer." disabled={locked} checked={v.hr_interview} onChange={(e) => set("hr_interview", e.target.checked)} />
    </div>
  );
}
