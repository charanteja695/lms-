import { DIFFICULTY_LABELS, PROBLEM_STATUS_LABELS, PROBLEM_TYPE_LABELS } from "@/modules/code-execution/common/labels";
import type { ProblemFilters as Filters } from "@/modules/code-execution/problems/types";
import { FilterBar, FilterSelect, FilterText } from "@/shared/ui";

const DIFFICULTY_OPTIONS = Object.entries(DIFFICULTY_LABELS).map(([value, label]) => ({ value, label }));
const TYPE_OPTIONS = Object.entries(PROBLEM_TYPE_LABELS).map(([value, label]) => ({ value, label }));
const STATUS_OPTIONS = Object.entries(PROBLEM_STATUS_LABELS).map(([value, label]) => ({ value, label }));
const SOLVED_OPTIONS = [
  { value: "true", label: "Solved" },
  { value: "false", label: "Not solved" },
];

interface ProblemFiltersProps {
  filters: Filters;
  canAuthor: boolean;
  activeCount: number;
  update(changes: Record<string, string | undefined>): void;
  reset(): void;
}

export function ProblemFilters({ filters, canAuthor, activeCount, update, reset }: ProblemFiltersProps) {
  return (
    <FilterBar
      search={filters.search ?? ""}
      onSearch={(value) => update({ search: value || undefined })}
      searchPlaceholder="Search by title"
      activeCount={activeCount}
      onReset={reset}
      primary={
        <>
          <FilterSelect label="Difficulty" value={filters.difficulty} options={DIFFICULTY_OPTIONS} onChange={(value) => update({ difficulty: value })} />
          <FilterSelect label="Type" value={filters.problem_type} options={TYPE_OPTIONS} onChange={(value) => update({ problem_type: value })} />
        </>
      }
      more={
        <>
          {canAuthor ? (
            <FilterSelect label="Status" value={filters.status} options={STATUS_OPTIONS} onChange={(value) => update({ status: value })} />
          ) : (
            <FilterSelect label="Progress" value={filters.solved === undefined ? undefined : String(filters.solved)} options={SOLVED_OPTIONS} onChange={(value) => update({ solved: value })} />
          )}
          <FilterText label="Tag" value={filters.tag} onChange={(value) => update({ tag: value })} placeholder="e.g. arrays" />
        </>
      }
    />
  );
}
