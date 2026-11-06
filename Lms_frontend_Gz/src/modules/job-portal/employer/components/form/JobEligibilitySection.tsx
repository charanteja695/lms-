import { CourseTitleCell } from "@/modules/catalog/common/components/CourseTitleCell";
import { useCourseOptions } from "@/modules/catalog/common/hooks/useCourseOptions";
import { useInstitutionDirectoryOptions } from "@/modules/job-portal/common/api/directoryApi";
import { PickedList } from "@/modules/job-portal/employer/components/form/PickedList";
import type { JobSectionProps } from "@/modules/job-portal/employer/components/form/JobBasicsSection";
import { Button, EntityPicker, Field, Input } from "@/shared/ui";

/** Who can apply: skills, experience, CGPA, graduation years, branches, course certificates and institutions. */
export function JobEligibilitySection({ values: v, set }: JobSectionProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Required Skills" required hint="Comma-separated skills (e.g. React, TypeScript, Node.js)." className="sm:col-span-2">
        {(p) => <Input {...p} placeholder="e.g. React, TypeScript, Node.js, SQL" value={v.required_skills} onChange={(e) => set("required_skills", e.target.value)} />}
      </Field>

      <Field label="Preferred / Good-to-have Skills" hint="Optional comma-separated skills." className="sm:col-span-2">
        {(p) => <Input {...p} placeholder="e.g. Docker, GraphQL, AWS" value={v.preferred_skills} onChange={(e) => set("preferred_skills", e.target.value)} />}
      </Field>

      <Field label="Minimum Experience (Years)" hint="0 for fresh graduates / entry level.">
        {(p) => <Input {...p} type="number" min={0} step="0.5" placeholder="0" value={v.experience_min_years} onChange={(e) => set("experience_min_years", e.target.value)} />}
      </Field>

      <Field label="Maximum Experience (Years)" hint="Leave empty for no upper limit.">
        {(p) => <Input {...p} type="number" min={0} step="0.5" placeholder="e.g. 3" value={v.experience_max_years} onChange={(e) => set("experience_max_years", e.target.value)} />}
      </Field>

      <Field label="Minimum CGPA" hint="Students below this CGPA cannot apply. Leave empty for no minimum (0.00 – 10.00).">
        {(p) => <Input {...p} type="number" min={0} max={10} step="0.01" placeholder="e.g. 7.50" value={v.min_cgpa} onChange={(e) => set("min_cgpa", e.target.value)} />}
      </Field>

      <Field label="Eligible Branches / Departments" hint="Comma-separated. Leave empty to allow all branches.">
        {(p) => <Input {...p} type="text" placeholder="e.g. Computer Science, Information Technology, Electronics" value={v.branches} onChange={(e) => set("branches", e.target.value)} />}
      </Field>

      <Field label="Graduation Year From">
        {(p) => <Input {...p} type="number" min={2000} max={2100} placeholder="e.g. 2024" value={v.graduation_min} onChange={(e) => set("graduation_min", e.target.value)} />}
      </Field>

      <Field label="Graduation Year Up To">
        {(p) => <Input {...p} type="number" min={2000} max={2100} placeholder="e.g. 2026" value={v.graduation_max} onChange={(e) => set("graduation_max", e.target.value)} />}
      </Field>

      <div className="sm:col-span-2">
        <PickedList
          label="Must Hold LMS Certificate In"
          hint="Only students with a verified completion certificate in these courses can apply."
          picked={v.certificate_courses || []}
          useOptions={useCourseOptions}
          renderLabel={(p) => <CourseTitleCell courseId={p.id} />}
          onChange={(next) => set("certificate_courses", next)}
        />
      </div>

      <div className="space-y-2 sm:col-span-2">
        <EntityPicker
          label="Minimum Test / Assessment Score In LMS Course"
          value=""
          useOptions={useCourseOptions}
          onChange={(id, label) => id && !(v.min_scores || []).some((s) => s.id === id) && set("min_scores", [...(v.min_scores || []), { id, label, min_percent: "60" }])}
        />
        {(v.min_scores || []).map((score) => (
          <div key={score.id} className="flex items-center gap-2 text-sm bg-slate-50 p-2.5 rounded-xl border border-slate-200">
            <span className="flex-1 truncate font-medium text-slate-800">{score.label || <CourseTitleCell courseId={score.id} />}</span>
            <span className="text-slate-500 text-xs">Min Score:</span>
            <Input aria-label="Minimum percent" className="w-20" type="number" min={0} max={100} value={score.min_percent} onChange={(e) => set("min_scores", (v.min_scores || []).map((s) => (s.id === score.id ? { ...s, min_percent: e.target.value } : s)))} />
            <span className="text-slate-500 font-bold">%</span>
            <Button variant="ghost" size="sm" onClick={() => set("min_scores", (v.min_scores || []).filter((s) => s.id !== score.id))}>Remove</Button>
          </div>
        ))}
      </div>

      <div className="sm:col-span-2">
        <PickedList
          label="Restrict to Students of Specific Institutions"
          hint="Leave empty to open the job to every institution on the platform."
          picked={v.institutions || []}
          useOptions={useInstitutionDirectoryOptions}
          onChange={(next) => set("institutions", next)}
        />
      </div>
    </div>
  );
}
