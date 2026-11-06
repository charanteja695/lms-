import type { CourseFilters as Filters } from "@/modules/catalog/courses/types";
import { Checkbox, FilterBar, FilterSelect } from "@/shared/ui";

/** "Newest first" is the server's default, so it is the placeholder rather than a duplicate option. */
const SORT_OPTIONS = [{ value: "asc", label: "Oldest first" }];

interface CourseFiltersProps {
  filters: Filters;
  activeCount: number;
  update(changes: Record<string, string | boolean | undefined>): void;
  reset(): void;
}

/** Search and the "More filters" panel for the courses list. */
export function CourseFilters({ filters, activeCount, update, reset }: CourseFiltersProps) {
  return (
    <FilterBar
      search={filters.search_text ?? ""}
      onSearch={(value) => update({ search_text: value || undefined })}
      searchPlaceholder="Search by title"
      activeCount={activeCount}
      onReset={reset}
      primary={<FilterSelect label="Sort" placeholder="Newest first" value={filters.sort_order} options={SORT_OPTIONS} onChange={(value) => update({ sort_order: value })} />}
      more={
        <Checkbox
          label="Include archived"
          checked={filters.include_archived ?? false}
          onChange={(event) => update({ include_archived: event.target.checked || undefined })}
        />
      }
    />
  );
}
