import type { LearningPathFilters as Filters } from "@/modules/catalog/learning-paths/types";
import { FilterBar, FilterSelect } from "@/shared/ui";

/** "Newest first" is the server's default, so it is the placeholder rather than a duplicate option. */
const SORT_OPTIONS = [{ value: "asc", label: "Oldest first" }];

interface LearningPathFiltersProps {
  filters: Filters;
  activeCount: number;
  update(changes: Record<string, string | undefined>): void;
  reset(): void;
}

export function LearningPathFilters({ filters, activeCount, update, reset }: LearningPathFiltersProps) {
  return (
    <FilterBar
      search={filters.search_text ?? ""}
      onSearch={(value) => update({ search_text: value || undefined })}
      searchPlaceholder="Search by title"
      activeCount={activeCount}
      onReset={reset}
      primary={<FilterSelect label="Sort" placeholder="Newest first" value={filters.sort_order} options={SORT_OPTIONS} onChange={(value) => update({ sort_order: value })} />}
    />
  );
}
