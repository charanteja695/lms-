import { useState } from "react";

import { useAnyEmployerOptions, useAnyInstitutionOptions } from "@/modules/user-management/common/hooks/useDirectoryOptions";
import { EntityPicker, Field, Select } from "@/shared/ui";

const KINDS = [
  { value: "institution", label: "Institution" },
  { value: "employer", label: "Company" },
];

/** A billing manager's organisation filter or choice: institutions and companies both receive invoices. */
export function OrgFilter({ value, label, onChange, required }: { value: string; label?: string; onChange: (id: string, label: string) => void; required?: boolean }) {
  const [kind, setKind] = useState("institution");
  return (
    <div className="grid gap-3 sm:grid-cols-[10rem_1fr]">
      <Field label="Type">{(p) => <Select {...p} value={kind} options={KINDS} onChange={(e) => { setKind(e.target.value); onChange("", ""); }} />}</Field>
      <EntityPicker
        label={kind === "employer" ? "Company" : "Institution"}
        required={required}
        value={value}
        selectedLabel={label}
        useOptions={kind === "employer" ? useAnyEmployerOptions : useAnyInstitutionOptions}
        onChange={onChange}
      />
    </div>
  );
}
