import { QUESTION_TYPE_LABELS, VERSION_STATUS_LABELS } from "@/modules/assessments/common/labels";
import type { QuestionFilters as Filters } from "@/modules/assessments/questions/types";
import { FilterBar, FilterSelect, FilterText } from "@/shared/ui";

const TYPE_OPTIONS = Object.entries(QUESTION_TYPE_LABELS).map(([value, label]) => ({ value, label }));
const STATUS_OPTIONS = Object.entries(VERSION_STATUS_LABELS).map(([value, label]) => ({ value, label }));

interface QuestionFiltersProps {
  filters: Filters;
  activeCount: number;
  update(changes: Record<string, string | undefined>): void;
  reset(): void;
}

export function QuestionFilters({ filters, activeCount, update, reset }: QuestionFiltersProps) {
  return (
    <FilterBar
      search={filters.search ?? ""}
      onSearch={(value) => update({ search: value || undefined })}
      searchPlaceholder="Search question text"
      activeCount={activeCount}
      onReset={reset}
      primary={
        <>
          <FilterSelect label="Type" value={filters.question_type} options={TYPE_OPTIONS} onChange={(value) => update({ question_type: value })} />
          <FilterSelect label="Version" value={filters.version_status} options={STATUS_OPTIONS} onChange={(value) => update({ version_status: value })} />
        </>
      }
      more={
        <>
          <FilterText label="Skill" value={filters.skill} onChange={(value) => update({ skill: value })} />
          <FilterText label="Topic" value={filters.topic} onChange={(value) => update({ topic: value })} />
          <FilterText label="Tag" value={filters.tag} onChange={(value) => update({ tag: value })} />
        </>
      }
    />
  );
}
