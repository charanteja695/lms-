import { toOptions } from "@/core/lib/options";
import type { ScoringMode } from "@/modules/assessments/questions/bodyTypes";
import { Field, Input, Select } from "@/shared/ui";

const SCORING_LABELS: Record<ScoringMode, string> = { all_or_nothing: "All or nothing", partial: "Weighted test cases" };

/** Shared by coding and sql questions — both point at a code-execution-service problem. */
export function CodingEditor({ problemId, languages, scoring, onProblemIdChange, onLanguagesChange, onScoringChange }: {
  problemId: string;
  languages: string;
  scoring: ScoringMode;
  onProblemIdChange: (value: string) => void;
  onLanguagesChange: (value: string) => void;
  onScoringChange: (scoring: ScoringMode) => void;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Problem ID" required hint="The code-execution-service problem this question judges against.">
        {(props) => <Input {...props} value={problemId} onChange={(event) => onProblemIdChange(event.target.value)} />}
      </Field>
      <Field label="Allowed languages" hint="Comma-separated codes. Leave blank to allow the problem's own list.">
        {(props) => <Input {...props} value={languages} onChange={(event) => onLanguagesChange(event.target.value)} placeholder="python3, cpp20" />}
      </Field>
      <Field label="Scoring">{() => <Select aria-label="Scoring" value={scoring} options={toOptions(SCORING_LABELS)} onChange={(event) => onScoringChange(event.target.value as ScoringMode)} />}</Field>
    </div>
  );
}
