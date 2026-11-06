import { COURSE_REQUEST_STATUS_LABELS } from "@/modules/subscriptions/common/labels";
import type { CourseRequestFilters as Filters } from "@/modules/subscriptions/course-requests/types";
import { Button, FilterRow, FilterSelect } from "@/shared/ui";

const STATUS_OPTIONS = Object.entries(COURSE_REQUEST_STATUS_LABELS).map(([value, label]) => ({ value, label }));

interface CourseRequestFiltersProps {
  filters: Filters;
  activeCount: number;
  update(changes: Record<string, string | undefined>): void;
  reset(): void;
}

/** No free-text search: subscription-service's list endpoints only filter by status. */
export function CourseRequestFilters({ filters, activeCount, update, reset }: CourseRequestFiltersProps) {
  return (
    <FilterRow activeCount={activeCount}>
      <FilterSelect label="Status" value={filters.status} options={STATUS_OPTIONS} onChange={(value) => update({ status: value })} />
      {activeCount > 0 && (
        <Button variant="ghost" onClick={reset}>
          Clear ({activeCount})
        </Button>
      )}
    </FilterRow>
  );
}
