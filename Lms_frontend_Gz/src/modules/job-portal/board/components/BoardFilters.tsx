import { toOptions } from "@/core/lib/options";
import { EMPLOYMENT_LABELS, LOCATION_TYPE_LABELS } from "@/modules/job-portal/common/labels";
import type { BoardFilters as Filters } from "@/modules/job-portal/board/types";
import { Button, Checkbox, FilterRow, FilterSelect, FilterText } from "@/shared/ui";

const SORT_OPTIONS = [
  { value: "relevance", label: "Best match" },
  { value: "newest", label: "Newest" },
  { value: "deadline", label: "Closing soon" },
  { value: "pay", label: "Highest pay" },
];

export function BoardFilters({ filters, activeCount, update, reset }: {
  filters: Filters;
  activeCount: number;
  update(changes: Record<string, string | boolean | undefined>): void;
  reset(): void;
}) {
  return (
    <FilterRow activeCount={activeCount} bordered={false}>
      <FilterText label="Search" value={filters.q} placeholder="Title, company…" onChange={(value) => update({ q: value })} />
      <FilterText label="Location" value={filters.location} onChange={(value) => update({ location: value })} />
      <FilterText label="Skill" value={filters.skill} onChange={(value) => update({ skill: value })} />
      <FilterSelect label="Type" value={filters.employment_type} options={toOptions(EMPLOYMENT_LABELS)} onChange={(value) => update({ employment_type: value })} />
      <FilterSelect label="Where" value={filters.location_type} options={toOptions(LOCATION_TYPE_LABELS)} onChange={(value) => update({ location_type: value })} />
      <FilterSelect label="Sort" value={filters.sort} options={SORT_OPTIONS} placeholder="Best match" onChange={(value) => update({ sort: value })} />
      <Checkbox label="Only jobs I'm eligible for" checked={filters.eligible_only ?? false} onChange={(e) => update({ eligible_only: e.target.checked || undefined })} />
      {activeCount > 0 && <Button variant="ghost" onClick={reset}>Clear ({activeCount})</Button>}
    </FilterRow>
  );
}
