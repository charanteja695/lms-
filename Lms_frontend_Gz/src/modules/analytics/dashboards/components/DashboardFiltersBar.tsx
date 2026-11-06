import { DAY_OPTIONS } from "@/modules/analytics/common/dashboards";
import type { DashboardFilters, DashboardKey } from "@/modules/analytics/common/types";
import { useAnyEmployerOptions, useAnyInstitutionOptions } from "@/modules/user-management/common/hooks/useDirectoryOptions";
import { EntityPicker, Field, Select } from "@/shared/ui";

export interface FilterState extends DashboardFilters {
  days: number;
  orgLabel?: string;
  employerLabel?: string;
}

/** Which dashboards take which organisation filter (docs/API.md). Only platform viewers see the pickers. */
const ORG_FILTER: Partial<Record<DashboardKey, "required" | "optional">> = { institution: "required", support: "optional", hiring: "optional", ai_usage: "optional", billing: "optional" };

export function DashboardFiltersBar({ dashboard, platform, value, onChange }: { dashboard: DashboardKey; platform: boolean; value: FilterState; onChange: (next: FilterState) => void }) {
  const org = platform ? ORG_FILTER[dashboard] : undefined;
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <Field label="Period">{(p) => <Select {...p} value={String(value.days)} options={DAY_OPTIONS} onChange={(e) => onChange({ ...value, days: Number(e.target.value) })} />}</Field>
      {org && (
        <EntityPicker
          label="Institution"
          required={org === "required"}
          placeholder={org === "required" ? "Choose an institution" : "All institutions"}
          value={value.organization_id ?? ""}
          selectedLabel={value.orgLabel}
          useOptions={useAnyInstitutionOptions}
          onChange={(id, label) => onChange({ ...value, organization_id: id || undefined, orgLabel: label })}
        />
      )}
      {platform && dashboard === "hiring" && (
        <EntityPicker
          label="Company"
          placeholder="All companies"
          value={value.employer_id ?? ""}
          selectedLabel={value.employerLabel}
          useOptions={useAnyEmployerOptions}
          onChange={(id, label) => onChange({ ...value, employer_id: id || undefined, employerLabel: label })}
        />
      )}
    </div>
  );
}
