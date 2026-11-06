import { SUBSCRIPTION_STATUS_LABELS } from "@/modules/subscriptions/common/labels";
import type { SubscriptionFilters as Filters } from "@/modules/subscriptions/subscriptions/types";
import { Button, FilterRow, FilterSelect } from "@/shared/ui";

const STATUS_OPTIONS = Object.entries(SUBSCRIPTION_STATUS_LABELS).map(([value, label]) => ({ value, label }));

interface SubscriptionFiltersProps {
  filters: Filters;
  activeCount: number;
  update(changes: Record<string, string | undefined>): void;
  reset(): void;
}

/** No free-text search: subscription-service's list endpoints only filter by status. */
export function SubscriptionFilters({ filters, activeCount, update, reset }: SubscriptionFiltersProps) {
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
