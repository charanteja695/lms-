import { toOptions } from "@/core/lib/options";
import { useInstitutionOptions } from "@/modules/user-management/common/hooks/useEntityOptions";
import { EMPLOYMENT_TYPE_LABELS, GENDER_LABELS, ROLE_LABELS, STATUS_LABELS } from "@/modules/user-management/common/labels";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import type { UserResource } from "@/modules/user-management/users/api/usersApi";
import { SORT_OPTIONS } from "@/modules/user-management/users/constants";
import type { UserFilters as Filters, UserSortColumn } from "@/modules/user-management/users/types";
import { EntityPicker, FilterBar, FilterDate, FilterSelect, FilterSelectField, FilterText } from "@/shared/ui";

type ListChange = Record<string, string | number | boolean | undefined>;

interface UserFiltersProps {
  resource: UserResource;
  filters: Filters;
  organizationLabel?: string;
  activeCount: number;
  update(changes: ListChange): void;
  reset(): void;
}

/** Search, quick filters and the "More filters" panel. Which filters exist comes from the server. */
export function UserFilters({ resource, filters, organizationLabel, activeCount, update, reset }: UserFiltersProps) {
  const isAdmins = resource === "admins";
  const { permissions } = usePermissions();
  const viewableRoles = permissions.users.view_roles;
  const sortValue = `${filters.sort_column ?? "created_time"}:${filters.sort_order ?? "desc"}`;
  const showsStudents = viewableRoles.includes("student");

  const changeSort = (value: string | undefined) => {
    const [column, order] = (value ?? "created_time:desc").split(":") as [UserSortColumn, "asc" | "desc"];
    const isDefault = column === "created_time" && order === "desc";
    update({ sort_column: isDefault ? undefined : column, sort_order: isDefault ? undefined : order });
  };

  return (
    <FilterBar
      search={filters.search_text ?? ""}
      onSearch={(value) => update({ search_text: value || undefined })}
      searchPlaceholder={isAdmins ? "Search name or email" : "Search name, email, phone, code"}
      activeCount={activeCount}
      onReset={reset}
      primary={
        <>
          {!isAdmins && viewableRoles.length > 1 && (
            <FilterSelect label="Role" value={filters.role} options={toOptions(ROLE_LABELS, viewableRoles)} onChange={(value) => update({ role: value })} />
          )}
          <FilterSelect
            label="Status"
            value={filters.status}
            options={toOptions(STATUS_LABELS, permissions.users.filter_statuses)}
            onChange={(value) => update({ status: value })}
          />
          <FilterSelect label="Sort" placeholder="Newest first" value={sortValue === "created_time:desc" ? undefined : sortValue} options={SORT_OPTIONS} onChange={changeSort} />
        </>
      }
      more={
        <>
          {!isAdmins && permissions.users.filter_by_institution && (
            <EntityPicker
              label="Institution"
              value={filters.organization_id ?? ""}
              selectedLabel={organizationLabel}
              useOptions={useInstitutionOptions}
              onChange={(value, label) => update({ organization_id: value || undefined, organization_label: label || undefined })}
            />
          )}
          {isAdmins && (
            <FilterSelectField
              label="Responsibility"
              value={filters.scope}
              options={permissions.admin_scopes.map((scope) => ({ value: scope, label: scope }))}
              onChange={(value) => update({ scope: value })}
            />
          )}
          {!isAdmins && (
            <>
              <FilterSelectField label="Gender" value={filters.gender} options={toOptions(GENDER_LABELS)} onChange={(value) => update({ gender: value })} />
              <FilterSelectField
                label="Employment type"
                value={filters.employment_type}
                options={toOptions(EMPLOYMENT_TYPE_LABELS)}
                onChange={(value) => update({ employment_type: value })}
              />
              <FilterText label="Department" value={filters.department} onChange={(value) => update({ department: value })} placeholder="e.g. Mathematics" />
            </>
          )}
          {showsStudents && (
            <>
              <FilterText label="Program" value={filters.program} onChange={(value) => update({ program: value })} placeholder="e.g. B.Tech" />
              <FilterText label="Branch" value={filters.branch} onChange={(value) => update({ branch: value })} placeholder="e.g. Computer Science" />
              <FilterText label="Section" value={filters.section} onChange={(value) => update({ section: value })} placeholder="A" />
              <FilterText
                label="Graduation year"
                value={filters.graduation_year ? String(filters.graduation_year) : undefined}
                onChange={(value) => update({ graduation_year: value })}
                placeholder="2027"
              />
            </>
          )}
          <FilterSelectField
            label="Email verified"
            value={filters.email_verified === undefined ? undefined : String(filters.email_verified)}
            options={[
              { value: "true", label: "Verified" },
              { value: "false", label: "Not verified" },
            ]}
            onChange={(value) => update({ email_verified: value === undefined ? undefined : value === "true" })}
          />
          <FilterDate label="Created from" value={filters.created_from} onChange={(value) => update({ created_from: value })} />
          <FilterDate label="Created to" value={filters.created_to} onChange={(value) => update({ created_to: value })} />
        </>
      }
    />
  );
}
