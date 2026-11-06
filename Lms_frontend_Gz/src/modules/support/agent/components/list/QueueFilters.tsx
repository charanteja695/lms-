import { toOptions } from "@/core/lib/options";
import { CATEGORY_LABELS, PRIORITY_LABELS, QUEUE_LABELS, STATUS_LABELS } from "@/modules/support/common/labels";
import type { QueueFilters as Filters } from "@/modules/support/agent/types";
import { Button, Checkbox, FilterRow, FilterSelect, FilterText } from "@/shared/ui";

const ASSIGNEE_OPTIONS = [
  { value: "me", label: "Mine" },
  { value: "unassigned", label: "Unassigned" },
];
const SORT_OPTIONS = [
  { value: "due", label: "Most urgent" },
  { value: "activity", label: "Recent activity" },
  { value: "created", label: "Newest" },
];

export function QueueFilters({ filters, activeCount, showQueue, update, reset }: {
  filters: Filters;
  activeCount: number;
  /** Only a manager (or the exam team + staff combined) sees more than one queue. */
  showQueue: boolean;
  update(changes: Record<string, string | boolean | undefined>): void;
  reset(): void;
}) {
  return (
    <FilterRow activeCount={activeCount}>
      <FilterText label="Subject" placeholder="Words in the subject" value={filters.q} onChange={(value) => update({ q: value })} />
      <FilterSelect label="Status" value={filters.status} options={toOptions(STATUS_LABELS)} placeholder="Active" onChange={(value) => update({ status: value })} />
      {showQueue && <FilterSelect label="Queue" value={filters.queue} options={toOptions(QUEUE_LABELS)} onChange={(value) => update({ queue: value })} />}
      <FilterSelect label="Priority" value={filters.priority} options={toOptions(PRIORITY_LABELS)} onChange={(value) => update({ priority: value })} />
      <FilterSelect label="Category" value={filters.category} options={toOptions(CATEGORY_LABELS)} onChange={(value) => update({ category: value })} />
      <FilterSelect label="Assignee" value={filters.assignee} options={ASSIGNEE_OPTIONS} placeholder="Anyone" onChange={(value) => update({ assignee: value })} />
      <FilterSelect label="Sort" value={filters.sort} options={SORT_OPTIONS} placeholder="Most urgent" onChange={(value) => update({ sort: value })} />
      <Checkbox label="SLA breached" checked={filters.breached ?? false} onChange={(event) => update({ breached: event.target.checked || undefined })} />
      {activeCount > 0 && (
        <Button variant="ghost" onClick={reset}>
          Clear ({activeCount})
        </Button>
      )}
    </FilterRow>
  );
}
