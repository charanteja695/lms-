import { useInstitutionOptions } from "@/modules/user-management/common/hooks/useEntityOptions";
import { EntityPicker, FilterSelectField, SearchInput } from "@/shared/ui";

const ACCESS_OPTIONS = [
  { value: "active", label: "Active" },
  { value: "suspended", label: "Access revoked" },
];

export interface ManageFilterValues {
  search_text?: string;
  status?: string;
  organization_id?: string;
  organization_label?: string;
}

/** Search, an institution picker (only where the server allows filtering by institution) and access. */
export function ManageFilters({ values, searchPlaceholder, showInstitution, update }: {
  values: ManageFilterValues;
  searchPlaceholder: string;
  showInstitution: boolean;
  update: (changes: ManageFilterValues) => void;
}) {
  return (
    <>
      <div className="min-w-0 space-y-1.5 sm:flex-1 sm:basis-64">
        <p className="text-sm font-medium text-slate-700">Search</p>
        <SearchInput value={values.search_text ?? ""} placeholder={searchPlaceholder} onChange={(value) => update({ search_text: value || undefined })} />
      </div>
      {showInstitution && (
        <div className="sm:w-64">
          <EntityPicker
            label="Institution"
            emptyLabel="All institutions"
            placeholder="Search institutions…"
            value={values.organization_id ?? ""}
            selectedLabel={values.organization_label}
            useOptions={useInstitutionOptions}
            onChange={(value, label) => update({ organization_id: value || undefined, organization_label: label || undefined })}
          />
        </div>
      )}
      <FilterSelectField label="Access" value={values.status} options={ACCESS_OPTIONS} onChange={(value) => update({ status: value })} />
    </>
  );
}
