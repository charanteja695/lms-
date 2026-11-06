import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { useDeleteAcademicItemMutation } from "@/modules/user-management/academics/api/academicsApi";
import type { StructureTarget } from "@/modules/user-management/academics/components/StructureItemDialog";
import type { AcademicRights, ClassSection, Department } from "@/modules/user-management/academics/types";
import { Button, ConfirmDialog, Icon } from "@/shared/ui";

/** A department with its programs; each program lists its sections by year. */
export function DepartmentCard({ organizationId, department, rights, onEdit, onOpenSection }: {
  organizationId: string;
  department: Department;
  rights: AcademicRights;
  onEdit: (target: StructureTarget) => void;
  onOpenSection: (section: ClassSection) => void;
}) {
  const notify = useNotify();
  const confirm = useConfirmAction();
  const [remove] = useDeleteAcademicItemMutation();
  const drop = (kind: "departments" | "programs", id: string, label: string) =>
    confirm.ask({ title: `Remove ${label}?`, description: "Only empty items can be removed.", confirmLabel: "Remove" }, async () => {
      await remove({ organizationId, kind, id }).unwrap().then(() => notify.success("Removed"), notify.apiError);
    });

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-card">
      <header className="flex flex-wrap items-center gap-3 px-5 py-4">
        <span className="flex h-11 min-w-11 max-w-28 shrink-0 items-center justify-center truncate rounded-xl bg-navy-950 px-2.5 text-xs font-bold tracking-wide text-white">{department.code}</span>
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-bold text-navy-950 sm:truncate">{department.name}</h2>
          <p className="text-xs text-slate-500">
            {department.head ? <>Head: <span className="font-medium text-slate-700">{department.head.full_name}</span></> : "No head of department yet"} · {department.programs.length} program
            {department.programs.length === 1 ? "" : "s"}
          </p>
        </div>
        {(rights.update || rights.delete) && (
          <div className="ml-auto flex items-center gap-1">
            {rights.update && <Button variant="ghost" size="icon" aria-label={`Edit ${department.name}`} onClick={() => onEdit({ kind: "departments", item: department })}><Icon name="edit" size={15} /></Button>}
            {rights.delete && <Button variant="ghost" size="icon" aria-label={`Remove ${department.name}`} onClick={() => drop("departments", department.department_id, department.name)}><Icon name="trash" size={15} /></Button>}
          </div>
        )}
      </header>

      <div className="space-y-3 border-t border-slate-100 bg-slate-50/70 px-4 py-4">
        {department.programs.length === 0 && <p className="px-1 text-sm text-slate-500">No programs yet. A program is a course of study, such as B.Tech Computer Science.</p>}
        {department.programs.map((program) => {
          const years = Array.from({ length: program.duration_years }, (_, i) => i + 1);
          return (
            <div key={program.program_id} className="rounded-xl border border-slate-200/80 bg-white p-4">
              <div className="flex flex-wrap items-center gap-2">
                <div className="min-w-0 basis-full sm:basis-auto sm:flex-1">
                  <p className="text-sm font-semibold text-navy-950 sm:truncate">{program.name}</p>
                  <p className="text-xs text-slate-500">{program.code} · {program.duration_years} years · {program.sections.length} section{program.sections.length === 1 ? "" : "s"}</p>
                </div>
                {(rights.create || rights.update || rights.delete) && (
                  <div className="flex items-center gap-1 sm:ml-0">
                    {rights.create && <Button variant="secondary" size="sm" icon="plus" onClick={() => onEdit({ kind: "sections", parent: program })}>Section</Button>}
                    {rights.update && <Button variant="ghost" size="icon" aria-label={`Edit ${program.name}`} onClick={() => onEdit({ kind: "programs", item: program, parent: department })}><Icon name="edit" size={15} /></Button>}
                    {rights.delete && <Button variant="ghost" size="icon" aria-label={`Remove ${program.name}`} onClick={() => drop("programs", program.program_id, program.name)}><Icon name="trash" size={15} /></Button>}
                  </div>
                )}
              </div>
              {program.sections.length > 0 && (
                <div className="mt-3 space-y-2">
                  {years.filter((year) => program.sections.some((s) => s.year_of_study === year)).map((year) => (
                    <div key={year} className="flex flex-wrap items-center gap-2">
                      <span className="w-14 shrink-0 text-xs font-semibold text-slate-500">Year {year}</span>
                      {program.sections.filter((s) => s.year_of_study === year).map((section) => (
                        <button
                          key={section.section_id}
                          type="button"
                          onClick={() => onOpenSection(section)}
                          className="group inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm transition-colors hover:border-brand-300 hover:bg-brand-50"
                        >
                          <span className="font-semibold text-navy-950">{section.name}</span>
                          <span className="text-xs tabular-nums text-slate-500">{section.student_count} student{section.student_count === 1 ? "" : "s"}</span>
                          <Icon name="chevronRight" size={14} className="text-slate-400 group-hover:text-brand-600" />
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
        {rights.create && (
          <button
            type="button"
            onClick={() => onEdit({ kind: "programs", parent: department })}
            className="flex w-full items-center justify-center gap-2 rounded-xl border-2 border-dashed border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-500 transition-colors hover:border-brand-300 hover:bg-brand-50/50 hover:text-brand-700"
          >
            <Icon name="plus" size={16} />
            Add a program to {department.code}
          </button>
        )}
      </div>
      <ConfirmDialog {...confirm.dialogProps} />
    </section>
  );
}
