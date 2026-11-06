import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useCreateAcademicItemMutation, useUpdateAcademicItemMutation } from "@/modules/user-management/academics/api/academicsApi";
import { teacherOptionsHook } from "@/modules/user-management/academics/hooks/useAcademicsOptions";
import type { ClassSection, Department, Program } from "@/modules/user-management/academics/types";
import { Button, EntityPicker, Field, Input, Modal, Select } from "@/shared/ui";

/** What the dialog adds or edits; `parent` is the department of a new program or the program of a new section. */
export type StructureTarget =
  | { kind: "departments"; item?: Department }
  | { kind: "programs"; item?: Program; parent: Department }
  | { kind: "sections"; item?: ClassSection; parent: Program };

const TITLES = { departments: "department", programs: "program", sections: "section" } as const;

/** Add or edit a department (with its head), a program (with its length) or a section (with its class teacher). */
export function StructureItemDialog({ organizationId, target, onClose }: { organizationId: string; target: StructureTarget; onClose: () => void }) {
  const notify = useNotify();
  const [create, { isLoading: creating }] = useCreateAcademicItemMutation();
  const [update, { isLoading: updating }] = useUpdateAcademicItemMutation();
  const editing = Boolean(target.item);
  const [name, setName] = useState(target.item?.name ?? "");
  const [code, setCode] = useState(target.kind !== "sections" ? (target.item?.code ?? "") : "");
  const [years, setYears] = useState(String(target.kind === "programs" ? (target.item?.duration_years ?? 4) : target.kind === "sections" ? (target.item?.year_of_study ?? 1) : ""));
  const person = target.kind === "departments" ? target.item?.head : target.kind === "sections" ? target.item?.class_teacher : null;
  const [personId, setPersonId] = useState(person?.user_id ?? "");
  const [personLabel, setPersonLabel] = useState(person?.full_name ?? "");

  const body = () => {
    if (target.kind === "departments") return { name, code, head_user_id: personId || null };
    if (target.kind === "programs") return { name, code, duration_years: Number(years), ...(editing ? {} : { department_id: target.parent.department_id }) };
    return { name, year_of_study: Number(years), class_teacher_id: personId || null, ...(editing ? {} : { program_id: target.parent.program_id }) };
  };
  const id = target.kind === "departments" ? target.item?.department_id : target.kind === "programs" ? target.item?.program_id : target.item?.section_id;
  const save = () =>
    (id ? update({ organizationId, kind: target.kind, id, body: body() }) : create({ organizationId, kind: target.kind, body: body() }))
      .unwrap()
      .then(() => {
        notify.success(editing ? "Saved" : `${TITLES[target.kind][0]!.toUpperCase()}${TITLES[target.kind].slice(1)} added`);
        onClose();
      }, notify.apiError);

  const duration = target.kind === "sections" ? target.parent.duration_years : 8;
  return (
    <Modal
      open
      onClose={onClose}
      title={`${editing ? "Edit" : "Add"} ${TITLES[target.kind]}`}
      description={target.kind === "programs" ? `In ${target.parent.name}` : target.kind === "sections" ? `In ${target.parent.name}` : undefined}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={creating || updating} disabled={!name.trim() || (target.kind !== "sections" && !code.trim())} onClick={() => void save()}>
            {editing ? "Save" : "Add"}
          </Button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {target.kind === "sections" ? (
          <>
            <Field label="Year" required>
              {(p) => <Select {...p} value={years} options={Array.from({ length: duration }, (_, i) => ({ value: String(i + 1), label: `Year ${i + 1}` }))} onChange={(e) => setYears(e.target.value)} />}
            </Field>
            <Field label="Section" required hint="e.g. A">{(p) => <Input {...p} maxLength={20} value={name} onChange={(e) => setName(e.target.value)} />}</Field>
          </>
        ) : (
          <>
            <Field label="Name" required className="sm:col-span-2">
              {(p) => <Input {...p} maxLength={120} value={name} placeholder={target.kind === "departments" ? "Computer Science and Engineering" : "B.Tech Computer Science"} onChange={(e) => setName(e.target.value)} />}
            </Field>
            <Field label="Code" required hint="Short and unique here, e.g. CSE">{(p) => <Input {...p} maxLength={20} value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} />}</Field>
            {target.kind === "programs" && (
              <Field label="Length (years)" required>{(p) => <Input {...p} type="number" min={1} max={8} value={years} onChange={(e) => setYears(e.target.value)} />}</Field>
            )}
          </>
        )}
        {target.kind !== "programs" && (
          <div className="sm:col-span-2">
            <EntityPicker
              label={target.kind === "departments" ? "Head of department" : "Class teacher"}
              hint="Optional. A staff member of this institution."
              value={personId}
              selectedLabel={personLabel || undefined}
              useOptions={teacherOptionsHook(organizationId)}
              onChange={(value, label) => {
                setPersonId(value);
                setPersonLabel(label);
              }}
            />
          </div>
        )}
      </div>
    </Modal>
  );
}
