import { SESSION_STATUS_LABELS } from "@/modules/proctoring/common/labels";
import type { MonitorFilters as Filters } from "@/modules/proctoring/monitor/types";
import { Button, Checkbox, FilterRow, FilterSelect } from "@/shared/ui";

const STATUS_OPTIONS = Object.entries(SESSION_STATUS_LABELS).map(([value, label]) => ({ value, label }));
const RISK_OPTIONS = [
  { value: "25", label: "25+" },
  { value: "50", label: "50+" },
  { value: "75", label: "75+" },
];

interface MonitorFiltersProps {
  filters: Filters;
  activeCount: number;
  update(changes: Record<string, string | boolean | undefined>): void;
  reset(): void;
}

export function MonitorFilters({ filters, activeCount, update, reset }: MonitorFiltersProps) {
  return (
    <FilterRow activeCount={activeCount}>
      <FilterSelect label="Status" value={filters.status} options={STATUS_OPTIONS} onChange={(value) => update({ status: value })} />
      <FilterSelect label="Min. risk" value={filters.min_risk != null ? String(filters.min_risk) : undefined} options={RISK_OPTIONS} onChange={(value) => update({ min_risk: value })} />
      <Checkbox label="Critical only" checked={filters.only_critical ?? false} onChange={(event) => update({ only_critical: event.target.checked || undefined })} />
      {activeCount > 0 && (
        <Button variant="ghost" onClick={reset}>
          Clear ({activeCount})
        </Button>
      )}
    </FilterRow>
  );
}
