import { formatDate } from "@/core/lib/format";
import { RELATIONSHIP_LABELS } from "@/modules/user-management/common/labels";
import type { StudentProfile } from "@/modules/user-management/users/types";
import { Badge, Card, DescriptionList } from "@/shared/ui";

export function StudentCard({ student }: { student: StudentProfile }) {
  return (
    <Card title="Student">
      <DescriptionList
        items={[
          { label: "Admission number", value: student.admission_number },
          { label: "Admission date", value: student.admission_date && formatDate(student.admission_date) },
          { label: "Program", value: student.program },
          { label: "Branch", value: student.branch },
          { label: "Year of study", value: student.year_of_study },
          { label: "Section", value: student.section },
          { label: "Graduation year", value: student.graduation_year },
          { label: "CGPA", value: student.cgpa },
        ]}
      />
      <h3 className="mb-3 mt-6 text-sm font-semibold text-slate-900">Guardians</h3>
      {student.guardians.length === 0 ? (
        <p className="text-sm text-slate-500">No guardians recorded.</p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {student.guardians.map((guardian) => (
            <li key={guardian.phone} className="rounded-lg border border-slate-200 p-4 text-sm">
              <p className="flex items-center gap-2 font-medium text-slate-900">
                {guardian.full_name}
                {guardian.is_primary && <Badge tone="indigo">Primary</Badge>}
              </p>
              <p className="text-slate-500">
                {RELATIONSHIP_LABELS[guardian.relationship]}
                {guardian.occupation && ` · ${guardian.occupation}`}
              </p>
              <p className="mt-2 text-slate-700">{guardian.phone}</p>
              {guardian.email && <p className="text-slate-700">{guardian.email}</p>}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
