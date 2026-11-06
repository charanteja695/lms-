import { useMemo, useState } from "react";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { useDeleteAcademicItemMutation, useGetSectionStudentsQuery, usePlaceStudentsMutation } from "@/modules/user-management/academics/api/academicsApi";
import { studentOptionsHook } from "@/modules/user-management/academics/hooks/useAcademicsOptions";
import type { AcademicRights, ClassSection } from "@/modules/user-management/academics/types";
import { Button, ConfirmDialog, Drawer, EmptyState, EntityPicker, Icon, PageHeader, Spinner } from "@/shared/ui";

/** A section's students in a slide-over: add students (moving them from any other section) or take them out. */
export function SectionRoster({ organizationId, section, rights, onEdit, onClose }: {
  organizationId: string;
  section: ClassSection;
  rights: AcademicRights;
  onEdit: () => void;
  onClose: () => void;
}) {
  const notify = useNotify();
  const confirm = useConfirmAction();
  const { data, isLoading } = useGetSectionStudentsQuery({ organizationId, sectionId: section.section_id });
  const [place, { isLoading: placing }] = usePlaceStudentsMutation();
  const [remove] = useDeleteAcademicItemMutation();
  const [picked, setPicked] = useState<{ id: string; label: string } | null>(null);
  const useStudents = useMemo(() => studentOptionsHook(organizationId), [organizationId]);
  const students = data?.students ?? [];
  const current = data?.section ?? section;

  const change = (body: { add?: string[]; remove?: string[] }, done: string) =>
    place({ organizationId, sectionId: section.section_id, ...body })
      .unwrap()
      .then(() => notify.success(done), notify.apiError);

  return (
    <Drawer onClose={onClose} size="md">
      <div className="flex-1 px-5 py-6 sm:px-8">
        <PageHeader
          title={`Section ${current.label}`}
          description={`${current.student_count} student${current.student_count === 1 ? "" : "s"}${current.class_teacher ? ` · class teacher ${current.class_teacher.full_name}` : ""}`}
          actions={rights.update ? <Button variant="ghost" size="icon" aria-label="Edit section" onClick={onEdit}><Icon name="edit" size={16} /></Button> : undefined}
        />
        {rights.update && (
          <div className="mb-6 grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-2">
            <div className="min-w-0 flex-1">
              <EntityPicker
                label="Add a student"
                value={picked?.id ?? ""}
                selectedLabel={picked?.label}
                useOptions={useStudents}
                onChange={(id, label) => setPicked(id ? { id, label } : null)}
              />
            </div>
            <Button
              className="mt-[26px]"
              icon="plus"
              loading={placing}
              disabled={!picked}
              onClick={() => picked && void change({ add: [picked.id] }, `${picked.label} added`).then(() => setPicked(null))}
            >
              Add
            </Button>
            <p className="col-span-2 mt-1.5 text-xs text-slate-500">A student already in another section moves here.</p>
          </div>
        )}
        {isLoading ? (
          <div className="flex justify-center py-16"><Spinner /></div>
        ) : students.length === 0 ? (
          <EmptyState icon="users" title="No students in this section" description={rights.update ? "Add students above." : undefined} />
        ) : (
          <ul className="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200/80 bg-white">
            {students.map((student) => (
              <li key={student.user_id} className="flex items-center gap-3 px-4 py-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-bold text-brand-700 ring-1 ring-brand-100">
                  {student.full_name.split(" ").map((part) => part[0]).slice(0, 2).join("")}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-navy-950">{student.full_name}</span>
                  <span className="block truncate text-xs text-slate-500">{[student.admission_number, student.email].filter(Boolean).join(" · ")}</span>
                </span>
                {rights.update && (
                  <Button variant="ghost" size="sm" onClick={() => void change({ remove: [student.user_id] }, `${student.full_name} taken out`)}>Take out</Button>
                )}
              </li>
            ))}
          </ul>
        )}
        {rights.delete && students.length === 0 && !isLoading && (
          <div className="mt-6 flex justify-end">
            <Button
              variant="danger"
              icon="trash"
              onClick={() =>
                confirm.ask({ title: `Remove section ${current.label}?`, description: "The section is empty, so nothing else changes.", confirmLabel: "Remove" }, async () => {
                  await remove({ organizationId, kind: "sections", id: section.section_id }).unwrap().then(() => {
                    notify.success("Section removed");
                    onClose();
                  }, notify.apiError);
                })
              }
            >
              Remove section
            </Button>
          </div>
        )}
      </div>
      <ConfirmDialog {...confirm.dialogProps} />
    </Drawer>
  );
}
